from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_env_prepare_packages_list_path(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool(
        "env.prepare",
        {"packages": ["pytest", "pytest-cov"], "create": False, "install": False},
    )
    assert out.get("ok") is True and isinstance(out.get("plan"), dict)


## Note: line 723 covered via existing tests; keeping minimal here


def test_rules_enforce_parse_error_on_config_yaml(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # minimal compiled rules file
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/rules_compiled.json").write_text("{}", encoding="utf-8")
    # create invalid assistant.yaml to trigger parse except branch
    (tmp_path / ".mcp/assistant.yaml").write_text(": {", encoding="utf-8")
    out = srv._call_tool("rules.enforce", {})
    assert out.get("ok") is True


def test_rules_onboard_size_heuristics_safe_exception(
    tmp_path: Path, monkeypatch
) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # Monkeypatch Path.rglob to raise so except branch executes
    from pathlib import Path as _P

    real_rglob = _P.rglob

    def _boom(self, pattern):
        raise OSError("boom")

    monkeypatch.setattr(_P, "rglob", _boom)
    out = srv._call_tool(
        "rules.onboard", {"scenario": "personal", "complexity": "small"}
    )
    assert out.get("ok") is True
    # restore for safety
    monkeypatch.setattr(_P, "rglob", real_rglob)


def test_prompts_enabled_defensive_branch(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # Corrupt cfg to non-dict to trigger except branch -> disabled
    srv.cfg = "oops"  # type: ignore[assignment]
    r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "prompts/list"})
    assert r.get("result", {}).get("prompts") == []


def test_ide_scaffold_unknown_editor_errors(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    with pytest.raises(ValueError):
        srv._call_tool("ide.scaffold", {"editor": "unknown"})


def test_env_diagnose_license_import_error(tmp_path: Path, monkeypatch) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # Patch module to inject fake license_utils whose verify_license raises
    fake = SimpleNamespace(
        verify_license=lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    sys.modules["mcp_rules_assistant.license_utils"] = fake  # type: ignore[assignment]
    out = srv._call_tool("env.diagnose", {})
    assert out.get("ok") is True and out.get("license", {}).get("ok") in (False, None)
