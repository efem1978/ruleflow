from __future__ import annotations

import os
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def chdir(path: Path):
    class _Ctx:
        def __enter__(self):
            self._old = Path.cwd()
            os.chdir(path)
            return path

        def __exit__(self, exc_type, exc, tb):
            os.chdir(self._old)

    return _Ctx()


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_rules_resources_read_returns_error_when_missing(tmp_path: Path) -> None:
    with chdir(tmp_path):
        srv = JsonRpcServer()
        rlist = srv.handle(_req("resources/list"))
        compiled_uri = next(r.get("uri") for r in rlist.get("result", {}).get("resources", []) if str(r.get("uri")).endswith("/compiled"))
        # 注意：直接访问 rules 资源会报错（尚未摄取）
        res = srv.handle(_req("resources/read", {"uri": compiled_uri}))
        assert "error" in res and res["error"].get("message")
