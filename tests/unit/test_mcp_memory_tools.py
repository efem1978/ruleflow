from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer
from mcp_rules_assistant.memory import MemoryManager


def test_memory_append_and_snapshot(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    srv.mm = MemoryManager(tmp_path, window=3, max_bytes=4096)
    # append 3 turns, ensure window respected
    for i in range(5):
        srv._call_tool("memory.append_turn", {"role": "user", "content": f"问{i}"})
        srv._call_tool(
            "memory.append_turn",
            {"role": "assistant", "content": f"答{i}：计划 与 下一步"},
        )
    snap = srv._call_tool("memory.snapshot", {})
    assert isinstance(snap, dict)
    turns = snap.get("turns", [])
    assert len(turns) <= 6  # 3 rounds → up to 6 turns
    assert "summary" in snap


def test_memory_compress_on_size(tmp_path: Path) -> None:
    mm = MemoryManager(project_root=tmp_path, window=10, max_bytes=1200)
    long = "A" * 2000
    # push older long entries
    for _ in range(6):
        mm.append_turn("assistant", long, {})
    snap = mm.snapshot()
    total_len = len(
        (snap.get("summary") or "")
        + "".join(t.get("content", "") for t in snap.get("turns", []))
    )
    assert total_len < 2000 * 6  # compressed


def test_project_links_and_resource(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    srv.mm = MemoryManager(tmp_path)
    out = srv._call_tool(
        "project.link", {"project": "projB", "task": "sync api", "note": "relates"}
    )
    assert out.get("ok") is True
    # list and read links resource
    rlist = srv.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}}
    )
    uris = [r.get("uri") for r in rlist.get("result", {}).get("resources", [])]
    link_uri = next(u for u in uris if str(u).endswith("/links"))
    res = srv.handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "resources/read",
            "params": {"uri": link_uri},
        }
    )
    txt = res.get("result", {}).get("text", "{}")
    import json

    data = json.loads(txt)
    assert isinstance(data.get("links"), list) and data["links"]
