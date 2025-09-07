from __future__ import annotations

from pathlib import Path

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_onboard_detect_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    monkeypatch.setattr(JsonRpcServer, "_tool_project_detect", lambda self: (_ for _ in ()).throw(RuntimeError("boom")))  # type: ignore[no-untyped-call]
    out = srv._call_tool("rules.onboard", {"apply": False})
    assert out.get("ok") is True
    assert out.get("language") == "python"


def test_onboard_yaml_read_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import yaml as _yaml

    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # Make yaml.safe_load raise to hit except path
    monkeypatch.setattr(_yaml, "safe_load", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bad yaml")))  # type: ignore[no-untyped-call]
    out = srv._call_tool("rules.onboard", {"apply": True})
    assert out.get("ok") is True
    assert out.get("applied") in (True, False)  # write may still succeed or be skipped


def test_onboard_write_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path as _P

    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # Pre-create config to avoid ensure_project_config writing during patch
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        "performance:\n  on_push: {coverage: {min_module: 0.9}, mutation_test: false}\n",
        encoding="utf-8",
    )
    # Make Path.write_text raise to mark applied=False
    monkeypatch.setattr(_P, "write_text", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("io error")))  # type: ignore[no-untyped-call]
    out = srv._call_tool("rules.onboard", {"apply": True})
    assert out.get("ok") is True
    assert out.get("applied") is False
