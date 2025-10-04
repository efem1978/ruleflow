from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.memory import MemoryManager


def test_memory_summary_skips_non_dict(tmp_path: Path) -> None:
    mem = tmp_path / ".mcp" / "memory.json"
    mem.parent.mkdir(parents=True, exist_ok=True)
    # 将非字典 turn 放在“窗口范围内”的靠前位置，确保 _summarize 命中 continue 分支
    data = {
        "turns": [
            "bad-non-dict",
            {"role": "user", "content": "请生成计划", "meta": {}},
        ],
        "summary": "",
        "links": [],
    }
    mem.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    mm = MemoryManager(project_root=tmp_path, window=3)
    # 追加一条使其触发 summarize，且窗口覆盖到前面的非字典 turn
    mm.append_turn("assistant", "计划：A；下一步：B", {})
    snap = mm.snapshot()
    assert isinstance(snap.get("summary"), str)
    # 摘要应包含“计划/下一步”等关键词，且过程中未因非字典 turn 报错
    assert "计划" in snap.get("summary", "") or "下一步" in snap.get("summary", "")
