from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_diagnose_json_contains_hooks_and_ci(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=str(tmp_path)):
        # create minimal structure in current CWD
        Path(".mcp").mkdir(parents=True, exist_ok=True)
        Path(".github/workflows").mkdir(parents=True, exist_ok=True)
        Path(".github/workflows/ci.yml").write_text("name: CI", encoding="utf-8")
        Path(".git/hooks").mkdir(parents=True, exist_ok=True)
        Path(".git/hooks/pre-commit").write_text("#!/bin/sh", encoding="utf-8")
        r = runner.invoke(app, ["diagnose", "--json"])
        assert r.exit_code == 0
        import json

        d = json.loads(r.stdout)
        assert isinstance(d.get("hooks"), dict)
        assert d["hooks"].get("installed") is True
        assert isinstance(d.get("ci"), dict) and d["ci"].get("workflow_exists") is True
