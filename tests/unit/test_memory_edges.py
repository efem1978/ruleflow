from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.memory import DEFAULT_MEMORY_FILE, MemoryManager


def test_add_link_with_nonlist_links(tmp_path: Path) -> None:
    # seed invalid links value to trigger normalization path
    p = tmp_path / DEFAULT_MEMORY_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"turns": [], "summary": "", "links": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    mm = MemoryManager(tmp_path)
    mm.add_link("projX", "task-1", "rel")
    data = mm.snapshot()
    assert isinstance(data.get("links"), list) and data.get("links")


def test_compress_trims_meta_and_content(tmp_path: Path) -> None:
    mm = MemoryManager(tmp_path, window=10, max_bytes=600)
    # craft big old turn and small new turns
    big_meta = {f"k{i}": "x" * 50 for i in range(30)}
    mm.append_turn("assistant", "A" * 300, big_meta)
    for i in range(4):
        mm.append_turn("user", f"u{i}")
        mm.append_turn("assistant", f"a{i}")
    snap = mm.snapshot()
    turns = snap.get("turns", [])
    # first/older turn should be trimmed
    assert any(len(str(t.get("content", ""))) <= 120 for t in turns)


def test_compress_continue_on_nondict(tmp_path: Path) -> None:
    mm = MemoryManager(tmp_path, window=5, max_bytes=200)
    # craft turns with a non-dict old entry and large newer ones to trigger compression loop
    data = {
        "turns": [
            "bad_entry",
            {"role": "assistant", "content": "X" * 300, "meta": {}},
            {"role": "user", "content": "Y" * 300, "meta": {}},
        ],
        "summary": "",
        "links": [],
    }
    out = mm._compress_if_needed(data)
    assert isinstance(out, dict) and isinstance(out.get("turns"), list)
