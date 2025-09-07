from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def _write_cov_xml(path: Path) -> None:
    path.write_text(
        (
            "<coverage>\n"
            "  <packages><package><classes>\n"
            '    <class filename="a.py" line-rate="0.905" lines-valid="100" lines-covered="90"/>\n'
            '    <class filename="b.py" line-rate="0.920" lines-valid="100" lines-covered="92"/>\n'
            "  </classes></package></packages>\n"
            "</coverage>\n"
        ),
        encoding="utf-8",
    )


def test_tool_coverage_report_missing_file(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # Ensure no coverage.xml exists
    out = srv._call_tool("coverage.report", {})
    assert out.get("ok") is False


def test_tool_coverage_report_ok(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # Minimal config and coverage
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/assistant.yaml").write_text(
        "performance:\n  on_push:\n    coverage: {min_module: 0.90}\n",
        encoding="utf-8",
    )
    _write_cov_xml(tmp_path / "coverage.xml")
    out = srv._call_tool("coverage.report", {"within": 0.05, "top": 10})
    assert out.get("ok") is True
    assert isinstance(out.get("weak"), list)
    assert isinstance(out.get("groups"), list)
    assert isinstance(out.get("near"), list)


def test_tool_coverage_near_missing_and_ok(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # missing coverage.xml → ok False
    r1 = srv._call_tool("coverage.near", {"within": 0.03, "top": 5})
    assert r1.get("ok") is False
    # prepare coverage and config then near should be ok
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/assistant.yaml").write_text(
        "performance:\n  on_push:\n    coverage: {min_module: 0.90}\n",
        encoding="utf-8",
    )
    _write_cov_xml(tmp_path / "coverage.xml")
    r2 = srv._call_tool("coverage.near", {"within": 0.03, "top": 5})
    assert r2.get("ok") is True and isinstance(r2.get("near"), list)


def test_resource_coverage_report_json(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # prepare config and coverage
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/assistant.yaml").write_text(
        "performance:\n  on_push:\n    coverage: {min_module: 0.90}\n",
        encoding="utf-8",
    )
    _write_cov_xml(tmp_path / "coverage.xml")
    rlist = srv.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}}
    )
    rep_uri = next(
        r["uri"]
        for r in rlist["result"]["resources"]
        if str(r["uri"]).endswith("/report")
    )
    rep = srv.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/read",
            "params": {"uri": rep_uri},
        }
    )
    assert rep.get("result", {}).get("mimeType") == "application/json"
    data = json.loads(rep.get("result", {}).get("text") or "{}")
    assert data.get("ok") is True and isinstance(data.get("groups"), list)


def test_env_prepare_success_branch(monkeypatch, tmp_path: Path) -> None:
    # Simulate successful venv creation and pip installs without doing real work
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    calls = {"n": 0}
    from mcp_rules_assistant import mcp_server as msv

    def fake_run(*a, **k):
        calls["n"] += 1

        class P:
            returncode = 0

        return P()

    monkeypatch.setattr(msv, "run_cmd", fake_run)
    out = srv._call_tool("env.prepare", {"create": True, "install": True})
    assert out.get("ok") is True and out.get("created") and out.get("installed")
    assert calls["n"] >= 2


def test_resources_memory_and_ping(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    rlist = srv.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}}
    )
    mem_uri = next(
        r["uri"]
        for r in rlist["result"]["resources"]
        if str(r["uri"]).endswith("/rollup")
    )
    mem = srv.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/read",
            "params": {"uri": mem_uri},
        }
    )
    assert mem.get("result", {}).get("mimeType") == "application/json"
    pong = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}})
    assert pong.get("result", {}).get("ok") is True


def test_unknown_tool_raises(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    try:
        srv._call_tool("no_such_tool", {})
        assert False, "expected ValueError"
    except Exception as e:
        assert "Unknown tool" in str(e)


def test_config_update_invalid_payload_raises(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    try:
        srv._call_tool("config.update", {"data": 123})
        assert False, "expected error"
    except Exception as e:
        assert "data must be object" in str(e)
