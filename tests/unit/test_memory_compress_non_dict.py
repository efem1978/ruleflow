from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.memory import MemoryManager


def test_memory_compress_handles_non_dict_turns(tmp_path: Path) -> None:
    # Prepare a memory file with a non-dict element to hit the 'continue' branch
    mem = tmp_path / ".mcp/memory.json"
    mem.parent.mkdir(parents=True, exist_ok=True)
    # Prepare enough old turns (non-dict) so compression loop iterates over them
    data = {
        "turns": [
            "bad-non-dict",
            "bad-non-dict",
            "bad-non-dict",
            "bad-non-dict",
            "bad-non-dict",
        ],
        "summary": "",
        "links": [],
    }
    mem.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    # Small max_bytes to force compression path to run through the loop
    # window=1 ensures summarization only touches the last appended dict, avoiding errors
    mm = MemoryManager(project_root=tmp_path, window=1, max_bytes=128)
    mm.append_turn("user", "hello world", {"k": "v"})
    snap = mm.snapshot()
    assert isinstance(snap.get("turns"), list)
    assert len(snap.get("turns")) >= 1
