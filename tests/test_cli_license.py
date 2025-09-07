from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_license_status_and_activate(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()

    # Point HOME to tmp so that ~/.mcp/license.json is within tmp
    monkeypatch.setenv("HOME", str(tmp_path))

    # 1) status before activation -> activated False
    r1 = runner.invoke(app, ["license-status"])  # prints JSON-like dict
    assert r1.exit_code == 0
    assert "activated" in r1.stdout and "False" in r1.stdout

    # 2) activate with a sample license file
    src = tmp_path / "lic.json"
    src.write_text('{\n  "plan": "trial"\n}', encoding="utf-8")
    r2 = runner.invoke(app, ["license-activate", "--file", str(src)])
    assert r2.exit_code == 0
    assert "activated" in r2.stdout and "True" in r2.stdout

    # 3) status after activation -> activated True
    r3 = runner.invoke(app, ["license-status"])  # now it should exist
    assert r3.exit_code == 0
    assert "activated" in r3.stdout and "True" in r3.stdout
