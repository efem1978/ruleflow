from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_mcp_project_and_memory_and_rules_init(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # project.detect
    d = srv._call_tool("project.detect", {})
    assert d.get("language") in ("python", "unknown")
    # memory.toggle_auto + snapshot
    t1 = srv._call_tool("memory.toggle_auto", {"on": True})
    assert t1.get("ok") is True and t1.get("auto") is True
    snap = srv._call_tool("memory.snapshot", {})
    assert isinstance(snap.get("turns"), list)
    # rules.init
    rinit = srv._call_tool(
        "rules.init",
        {"scenario": "enterprise", "complexity": "large", "devMode": "tdd"},
    )
    assert "thresholds" in rinit and "enterprise" in json.dumps(rinit)

    # env.diagnose
    diag = srv._call_tool("env.diagnose", {})
    assert diag.get("ok") is True and "python_version" in diag


def test_mcp_rules_resources_after_ingest(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # write a minimal rules doc and ingest it via tool
    d = tmp_path / "r.md"
    d.write_text("- 覆盖率 90%\n- 禁止 skip/xfail\n", encoding="utf-8")
    ing = srv._call_tool("rules.ingest", {"paths": [str(d)]})
    assert ing.get("files") == 1
    # list resources and read compiled / compiled.json / suggestions
    rlist = srv.handle(_req("resources/list"))
    uris = [r.get("uri") for r in rlist.get("result", {}).get("resources", [])]
    comp_uri = next(u for u in uris if str(u).endswith("/compiled"))
    comp_json_uri = next(u for u in uris if str(u).endswith("/compiled.json"))
    sugg_uri = next(u for u in uris if str(u).endswith("/suggestions"))
    # compiled markdown
    r_comp = srv.handle(_req("resources/read", {"uri": comp_uri}))
    assert r_comp.get("result", {}).get("mimeType") == "text/markdown"
    text_md = r_comp.get("result", {}).get("text") or ""
    assert "Project Rules" in text_md or "项目规则" in text_md
    # compiled json
    r_cj = srv.handle(_req("resources/read", {"uri": comp_json_uri}))
    assert r_cj.get("result", {}).get("mimeType") == "application/json"
    data = json.loads(r_cj.get("result", {}).get("text") or "{}")
    assert isinstance(data.get("policy"), dict)
    # suggestions markdown (may be empty but should exist)
    # suggestions file may not be produced; write a simple one to ensure path exists
    (tmp_path / ".mcp/rules_suggestions.md").write_text(
        "# Suggestions\n", encoding="utf-8"
    )
    r_s = srv.handle(_req("resources/read", {"uri": sugg_uri}))
    assert r_s.get("result", {}).get("mimeType") == "text/markdown"


def test_mcp_tools_env_and_config_and_ci_and_enforce(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # env.prepare create only (no install to keep fast)
    out = srv._call_tool("env.prepare", {"create": True, "install": False})
    assert out.get("ok") is True and Path(out.get("venv") or "").exists()
    # plan.update and plan.set
    srv._call_tool("plan.update", {"text": "# 计划\n- 状态: planned\n"})
    srv._call_tool("plan.set", {"status": "in_progress", "current": "X", "next": "Y"})
    # git.install_hooks
    gi = srv._call_tool("git.install_hooks", {})
    assert gi.get("ok") is True
    # nl.command mapping
    nl = srv._call_tool("nl.command", {"text": "生成CI 并校验"})
    assert nl.get("ok") is True and isinstance(
        nl.get("parsed", {}).get("tool"), (str, type(None))
    )
    # config.get + update
    cfg = srv._call_tool("config.get", {"section": None})
    assert cfg.get("ok") is True and isinstance(cfg.get("config"), dict)
    upd = srv._call_tool(
        "config.update", {"data": {"hadolint": True, "semgrep_config": "auto"}}
    )
    assert upd.get("ok") is True and upd.get("ci", {}).get("hadolint") is True
    # ci.generate + validate + autofix
    cg = srv._call_tool("ci.generate", {})
    assert cg.get("ok") is True and Path(cg.get("path") or "").exists()
    cv = srv._call_tool("ci.validate", {})
    assert cv.get("ok") is True and cv.get("checks", {}).get("exists") is True
    ca = srv._call_tool("ci.autofix", {})
    assert ca.get("ok") is True and Path(ca.get("path") or "").exists()
    # rules.enforce requires compiled rules
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/rules_compiled.json").write_text(
        '{"policy": {"coverage.min_module": 0.91}}', encoding="utf-8"
    )
    en = srv._call_tool("rules.enforce", {})
    assert en.get("ok") is True and "coverage.min_module" in "\n".join(
        en.get("enforced", []) or []
    )


def test_mcp_tool_error_paths(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # project.switch (no-op)
    sw = srv._call_tool("project.switch", {})
    assert sw.get("ok") is True
    # rules.ingest requires paths
    try:
        srv._call_tool("rules.ingest", {"paths": []})
        assert False, "expected error"
    except Exception as e:
        assert "paths" in str(e)
    # rules.validate callable even when no compiled rules
    _ = srv._call_tool("rules.validate", {})
    # rules.enforce invalid compiled rules
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/rules_compiled.json").write_text(
        "{invalid json", encoding="utf-8"
    )
    try:
        srv._call_tool("rules.enforce", {})
        assert False, "expected error"
    except Exception as e:
        assert "invalid compiled rules" in str(e)
