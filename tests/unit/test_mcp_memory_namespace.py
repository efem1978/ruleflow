from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_memory_namespace_resources_and_read(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    # write a namespaced memory file
    ns = "team"
    data = {
        "turns": [{"role": "user", "content": "hi", "meta": {}}],
        "summary": "s",
        "links": [],
    }
    (tmp_path / ".mcp" / f"memory.{ns}.json").write_text(
        json.dumps(data), encoding="utf-8"
    )
    # list resources should include the ns entry
    r = srv.handle(_req("resources/list", {}))
    resources = r.get("result", {}).get("resources", [])
    uris = [x.get("uri") for x in resources]
    ns_uri = next(u for u in uris if str(u).endswith(f"rollup?ns={ns}"))
    # read namespaced memory
    res = srv.handle(_req("resources/read", {"uri": ns_uri}))
    assert res.get("result", {}).get("mimeType") == "application/json"
    txt = res.get("result", {}).get("text", "{}")
    obj = json.loads(txt)
    assert obj.get("turns")


def test_memory_toggle_auto_namespace(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool("memory.toggle_auto", {"on": True, "project": "squadA"})
    assert out.get("ok") is True and out.get("namespace") in ("squadA", "default")
    # append and snapshot should operate on the namespaced file
    srv._call_tool("memory.append_turn", {"role": "user", "content": "hello"})
    snap = srv._call_tool("memory.snapshot", {})
    assert isinstance(snap.get("turns"), list)


def test_memory_namespace_invalid_and_missing(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # invalid namespace
    try:
        srv._call_tool("memory.toggle_auto", {"on": True, "project": "!@#"})
        assert False, "expected invalid namespace error"
    except Exception:
        pass
    # read missing namespace via JSON-RPC
    pid = srv._project_id()
    req = _req("resources/read", {"uri": f"memory://{pid}/rollup?ns=notfound"})
    out = srv.handle(req)
    err = out.get("error", {})
    # custom code for resource not found
    assert err.get("code") in (-32001, -32602)


def test_resources_read_unknown_uri(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv.handle(_req("resources/read", {"uri": "unknown://x"}))
    err = out.get("error", {})
    # -32000: Unknown resource uri (custom mapping)
    assert err.get("code") == -32000
