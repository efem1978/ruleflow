from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.fs_wrapper import FSGuard


def test_fs_guard_without_post_checks(tmp_path: Path) -> None:
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    # 显式关闭写入后检查，覆盖另一分支
    cfg.write_text("execution:\n  fs_guard_post_checks: false\n", encoding="utf-8")

    guard = FSGuard(project_root=tmp_path)
    rel = Path("hello.py")
    guard.write_text(rel, "x=1\n")
    assert (tmp_path / rel).exists()
