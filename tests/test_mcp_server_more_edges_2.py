from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_env_diagnose_reads_maxima(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    d = tmp_path / ".mcp"
    d.mkdir(parents=True, exist_ok=True)
    (d / "rules_compiled.json").write_text(
        '{"meta": {"maxima": {"coverage.max_module": 0.95}}}', encoding="utf-8",
    )
    out = srv._call_tool("env.diagnose", {})
    assert out.get("ok") is True and isinstance(out.get("maxima"), dict)


def test_rules_enforce_with_invalid_yaml(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # invalid assistant.yaml to trigger except path
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("::bad::", encoding="utf-8")
    # minimal compiled rules containing coverage
    (tmp_path / ".mcp/rules_compiled.json").write_text(
        '{"policy": {"coverage.min_module": 0.91}}', encoding="utf-8",
    )
    out = srv._call_tool("rules.enforce", {})
    assert out.get("ok") is True and any(
        str(s).startswith("coverage.min_module=") for s in (out.get("enforced") or [])
    )


def test_project_detect_python(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    d = srv._call_tool("project.detect", {})
    assert d.get("language") == "python"
