from __future__ import annotations

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id_: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}


def test_fs_apply_patch_files_must_be_array() -> None:
    srv = JsonRpcServer()
    res = srv.handle(
        _req(
            "tools/call",
            {"name": "fs.apply_patch", "arguments": {"files": "not-a-list"}},
        ),
    )
    assert "files 必须为数组" in res.get("error", {}).get("message", "")


def test_fs_apply_patch_item_must_be_object() -> None:
    srv = JsonRpcServer()
    res = srv.handle(
        _req(
            "tools/call",
            {"name": "fs.apply_patch", "arguments": {"files": [123]}},
        ),
    )
    assert "files[*] 必须为对象" in res.get("error", {}).get("message", "")


def test_fs_apply_patch_content_must_be_string() -> None:
    srv = JsonRpcServer()
    res = srv.handle(
        _req(
            "tools/call",
            {
                "name": "fs.apply_patch",
                "arguments": {"files": [{"path": "a.py", "content": 1}]},
            },
        ),
    )
    assert "content 必须为字符串" in res.get("error", {}).get("message", "")
