#!/usr/bin/env python3
"""
Generate a clean social preview image for RuleFlow with no version text.

Defaults:
- Size: 1280x640
- Background: vertical teal gradient
- Title: "RuleFlow"
- Subtitle: "Programming Rule Governance + Memory"
- Bullets: current value props
- Bottom bar: repository and quick install hint

Usage:
  python3 scripts/generate_social_preview.py \
      --out docs/assets/social_preview_ruleflow.png \
      --width 1280 --height 640

Optional font override:
  --font "/Library/Fonts/Arial.ttf"  (or any .ttf you prefer)

This script is self-contained and does not depend on the existing image.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    raise SystemExit(
        "[error] Pillow (PIL) is required. Install: python3 -m pip install pillow"
    )


TEAL_TOP = (17, 73, 82)  # #114952
TEAL_BOTTOM = (43, 179, 192)  # #2BB3C0
DARK_BAR = (12, 48, 55)
WHITE = (255, 255, 255)
MUTED = (230, 245, 245)
ACCENT = (255, 255, 255)


def resolve_font_path(user_font: Optional[str] = None) -> Optional[str]:
    """Return a TTF font path if available, otherwise None."""
    if user_font and Path(user_font).exists():
        return user_font
    candidates = [
        "/Library/Fonts/Arial.ttf",
        "/Library/Fonts/HelveticaNeue.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
        "assets/fonts/Inter-Regular.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    return None


def load_font(path: Optional[str], size: int) -> ImageFont.ImageFont:
    try:
        if path:
            return ImageFont.truetype(path, size)
    except Exception:
        pass
    return ImageFont.load_default()


def make_gradient(
    size: Tuple[int, int], top: Tuple[int, int, int], bottom: Tuple[int, int, int]
) -> Image.Image:
    w, h = size
    img = Image.new("RGB", (w, h), top)
    dr = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        dr.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def draw_text(
    img: Image.Image,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill=WHITE,
    anchor: Optional[str] = None,
    align: str = "left",
):
    d = ImageDraw.Draw(img)
    d.text(xy, text, font=font, fill=fill, anchor=anchor, align=align)


def add_shadow_text(
    img: Image.Image,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill=WHITE,
    shadow=(0, 0, 0),
    offset=(2, 2),
):
    d = ImageDraw.Draw(img)
    x, y = xy
    d.text((x + offset[0], y + offset[1]), text, font=font, fill=shadow)
    d.text((x, y), text, font=font, fill=fill)


def measure(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont
) -> Tuple[int, int]:
    """Return (w,h) for text using Pillow APIs across versions."""
    try:
        # Pillow >=8: preferred accurate bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])
    except Exception:
        try:
            # Older Pillow fallback
            return draw.textsize(text, font=font)  # type: ignore[attr-defined]
        except Exception:
            try:
                return font.getsize(text)  # type: ignore[attr-defined]
            except Exception:
                return (len(text) * 10, 20)


def build_image(width: int, height: int, font_path: Optional[str]) -> Image.Image:
    base = make_gradient((width, height), TEAL_TOP, TEAL_BOTTOM)

    # Title band: keep clean (no overlay to avoid any band artifacts)

    # Fonts (sizes scaled to width)
    font_path_resolved = resolve_font_path(font_path)

    def scale(sz):
        # scale relative to 1280 width
        return int(sz * (width / 1280))

    title_font = load_font(font_path_resolved, scale(120))
    subtitle_font = load_font(font_path_resolved, scale(44))
    body_font = load_font(font_path_resolved, scale(32))
    mono_font = load_font(font_path_resolved, scale(28))

    # Title
    pad_x = scale(56)
    y = scale(60)
    add_shadow_text(
        base,
        (pad_x, y),
        "RuleFlow",
        title_font,
        fill=WHITE,
        shadow=(0, 0, 0),
        offset=(3, 3),
    )

    # Subtitle
    y += scale(130)
    draw_text(
        base,
        (pad_x, y),
        "AI Pair Programming Rule Governance + Memory",
        subtitle_font,
        fill=MUTED,
    )

    # Bullets
    y += scale(70)
    bullets = [
        "Unified context memory across VS Code / Cursor / Web / CLI",
        "1-click installer with CLI + VS Code extension (MIT)",
        "Coverage guardrails: core ≥ 98%, others ≥ 95%",
    ]
    for b in bullets:
        draw_text(base, (pad_x, y), f"• {b}", body_font, fill=WHITE)
        y += scale(48)

    # Bottom bar with repo/install
    bar_h = scale(64)
    bar = Image.new("RGB", (width, bar_h), DARK_BAR)
    base.paste(bar, (0, height - bar_h))

    bottom_text = "git clone https://github.com/efem1978/ruleflow && bash install.sh"
    d = ImageDraw.Draw(base)
    tw, th = measure(d, bottom_text, mono_font)
    d.text(
        ((width - tw) // 2, height - bar_h + (bar_h - th) // 2),
        bottom_text,
        font=mono_font,
        fill=ACCENT,
    )

    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/assets/social_preview_ruleflow.png")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=640)
    ap.add_argument("--font", default=None)
    args = ap.parse_args()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    img = build_image(args.width, args.height, args.font)
    img.save(args.out, format="PNG")
    print(f"[ok] wrote {args.out} ({args.width}x{args.height})")


if __name__ == "__main__":
    main()
