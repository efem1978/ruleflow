from __future__ import annotations

import os
from pathlib import Path

import pytest

from mcp_rules_assistant.fs_wrapper import FSGuard


def test_symlink_write_strict_rejected(tmp_path: Path) -> None:
    target = tmp_path / "real.txt"
    target.write_text("orig", encoding="utf-8")
    link = tmp_path / "link.txt"
    os.symlink(target, link)

    guard = FSGuard(tmp_path)
    guard.cfg.setdefault("execution", {})["fs_guard_strict"] = True

    with pytest.raises(Exception):
        guard.write_text(Path("link.txt"), "new")


def test_symlink_write_non_strict_allows(tmp_path: Path) -> None:
    target = tmp_path / "real2.txt"
    target.write_text("orig", encoding="utf-8")
    link = tmp_path / "link2.txt"
    os.symlink(target, link)

    guard = FSGuard(tmp_path)
    # 默认非严格：应继续并写入到符号链接目标
    guard.cfg.setdefault("execution", {})["fs_guard_strict"] = False
    guard.write_text(Path("link2.txt"), "changed")
    assert target.read_text(encoding="utf-8") == "changed"
