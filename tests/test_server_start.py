from __future__ import annotations

import importlib

import mcp_rules_assistant.mcp_server as msv
import mcp_rules_assistant.server as srv


def test_server_start_calls_serve_stdio() -> None:
    called = {"ok": False}

    def fake_stdio():
        called["ok"] = True

    # Patch at source and reload server to bind the patched symbol
    msv.serve_stdio = fake_stdio  # type: ignore[attr-defined]
    importlib.reload(srv)
    srv.start()
    assert called["ok"] is True
