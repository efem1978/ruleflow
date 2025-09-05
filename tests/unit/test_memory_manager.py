from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.memory import MemoryManager


def test_memory_append_and_snapshot(tmp_path: Path) -> None:
    mm = MemoryManager(tmp_path, window=3)
    mm.append_turn("user", "请生成计划", {})
    mm.append_turn("assistant", "计划：下一步……", {})
    mm.append_turn("user", "继续", {})
    snap = mm.snapshot()
    assert len(snap.get("turns", [])) == 3
    assert "计划" in (snap.get("summary") or "")

