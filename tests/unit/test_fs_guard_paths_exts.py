from __future__ import annotations

from pathlib import Path

import yaml

from mcp_rules_assistant.fs_wrapper import FSGuard


def write_cfg(root: Path, cfg: dict) -> None:
    p = root / ".mcp/assistant.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def base_cfg() -> dict:
    return {
        "execution": {
            "allowed_write_prefixes": ["docs/"],
            "allowed_write_extensions": [".md"],
            "fs_guard_strict": False,
        }
    }


def test_fs_guard_allows_configured_prefix_and_ext(tmp_path: Path) -> None:
    cfg = base_cfg()
    write_cfg(tmp_path, cfg)
    g = FSGuard(project_root=tmp_path)
    p = Path("docs/readme.md")
    g.write_text(p, "hello")
    assert (tmp_path / p).read_text(encoding="utf-8") == "hello"


def test_fs_guard_blocks_when_strict_true(tmp_path: Path) -> None:
    cfg = base_cfg()
    cfg["execution"]["fs_guard_strict"] = True
    write_cfg(tmp_path, cfg)
    g = FSGuard(project_root=tmp_path)
    # Disallowed prefix triggers raise
    import pytest

    with pytest.raises(Exception):
        g.write_text(Path("src/x.md"), "x")

    # Allowed prefix but disallowed extension also triggers raise
    with pytest.raises(Exception):
        g.write_text(Path("docs/code.py"), "print()")


def test_fs_guard_soft_fail_when_strict_false(tmp_path: Path) -> None:
    cfg = base_cfg()
    # strict false -> soft allow even when prefix/ext disallowed
    write_cfg(tmp_path, cfg)
    g = FSGuard(project_root=tmp_path)
    # Disallowed prefix but strict false should not raise, file should still be written
    p = Path("src/unlisted.md")
    g.write_text(p, "ok")
    assert (tmp_path / p).read_text(encoding="utf-8") == "ok"
