from __future__ import annotations

from typer.testing import CliRunner

import mcp_rules_assistant.cli as cli


class _FakeSrv:
    def __init__(self):
        pass

    def _call_tool(self, name, args):
        return {"ok": False}


def test_cli_enforce_failure(monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(cli, "JsonRpcServer", _FakeSrv)  # type: ignore[attr-defined]
    r = runner.invoke(cli.app, ["enforce"])
    assert r.exit_code != 0
    assert "enforce" in (r.stdout or "").lower()


def test_cli_prepare_env_failure_with_packages(monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(cli, "JsonRpcServer", _FakeSrv)  # type: ignore[attr-defined]
    r = runner.invoke(cli.app, ["prepare-env", "--install", "--packages", "a,b"])
    assert r.exit_code != 0
    assert "env.prepare" in (r.stdout or "").lower()
