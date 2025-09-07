from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, TypedDict

from .fs_wrapper import atomic_write_text

PLAN_MD = Path(".mcp/plan.md")


DEFAULT_PLAN = (
    "# 项目计划 / Project Plan\n\n"
    "- 状态: planned\n"
    "- 当前步骤: （填写）\n"
    "- 下一步: （填写）\n"
    "- 风险与阻塞: （填写）\n"
)


def ensure_plan(project_root: Optional[Path] = None) -> Path:
    root = (project_root or Path.cwd()).resolve()
    path = root / PLAN_MD
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        atomic_write_text(path, DEFAULT_PLAN)
    return path


def read_plan(project_root: Optional[Path] = None) -> str:
    path = ensure_plan(project_root)
    return path.read_text(encoding="utf-8")


def write_plan(text: str, project_root: Optional[Path] = None) -> Path:
    path = ensure_plan(project_root)
    atomic_write_text(path, text)
    return path


def parse_plan(text: str) -> Tuple[str, str, str]:
    status = "planned"
    current = ""
    nxt = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- 状态:") or line.lower().startswith("- status:"):
            status = line.split(":", 1)[1].strip().lower()
        elif line.startswith("- 当前步骤:") or line.lower().startswith(
            "- current step:"
        ):
            current = line.split(":", 1)[1].strip()
        elif line.startswith("- 下一步:") or line.lower().startswith("- next:"):
            nxt = line.split(":", 1)[1].strip()
    return status, current, nxt


def update_plan_fields(
    project_root: Optional[Path] = None,
    *,
    status: Optional[str] = None,
    current: Optional[str] = None,
    nxt: Optional[str] = None,
) -> Path:
    text = read_plan(project_root)
    lines = text.splitlines()

    class UpdateSpec(TypedDict):
        cn: str
        en: str
        val: Optional[str]

    updates: list[UpdateSpec] = [
        {"cn": "- 状态:", "en": "- status:", "val": status},
        {"cn": "- 当前步骤:", "en": "- current step:", "val": current},
        {"cn": "- 下一步:", "en": "- next:", "val": nxt},
    ]

    for item in updates:
        val = item["val"]
        if val is None:
            continue
        cn: str = item["cn"]
        en: str = item["en"].lower()
        replaced = False
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith(cn) or s.lower().startswith(en):
                lines[i] = f"{cn} {val}"
                replaced = True
                break
        if not replaced:
            lines.append(f"{cn} {val}")

    # Ensure trailing newline and handle empty file gracefully
    if lines:
        new_text = "\n".join(lines)
        if not new_text.endswith("\n"):
            new_text += "\n"
    else:
        new_text = "\n"
    return write_plan(new_text, project_root)
