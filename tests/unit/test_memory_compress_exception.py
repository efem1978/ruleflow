from __future__ import annotations

from mcp_rules_assistant.memory import MemoryManager


def test_compress_if_needed_exception_path(tmp_path):
    mm = MemoryManager(tmp_path, window=2, max_bytes=10)

    class Bad:
        pass

    data = {
        "turns": [{"role": "assistant", "content": "x", "meta": {}}],
        "summary": "",
        "links": [],
        "bad": Bad(),
    }
    # Directly call internal to trigger json serialization failure at first dump
    out = mm._compress_if_needed(data)  # should swallow and return original
    assert out is data
