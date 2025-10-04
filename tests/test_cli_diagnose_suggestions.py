from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_diagnose_suggestions_present_when_missing_items(tmp_path: Path) -> None:
    r = CliRunner().invoke(
        app, ["diagnose", "--json"], env={"PYTHONPATH": str(tmp_path)},
    )
    # We run in an isolated test workspace anyway; re-run in isolated filesystem
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=str(tmp_path)):
        out = runner.invoke(app, ["diagnose", "--json"]).stdout
        import json

        d = json.loads(out)
        # In empty workspace, we expect at least one suggestion (e.g., install-hooks / generate-ci / run pytest)
        sugg = d.get("suggestions") or []
        assert isinstance(sugg, list) and len(sugg) >= 1
