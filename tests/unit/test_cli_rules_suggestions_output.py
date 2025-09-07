from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_rules_suggestions_text_and_csv(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        comp = {
            "policy": {},
            "conflicts": [],
            "suggestions": [
                {"key": "test.no_skip_xfail", "action": "enforce", "severity": "must"},
                {
                    "key": "coverage.min_module",
                    "action": "enforce",
                    "severity": "must",
                    "value": 0.9,
                },
            ],
        }
        p = Path(".mcp/rules_compiled.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(comp), encoding="utf-8")

        r1 = runner.invoke(app, ["rules-suggestions"])  # default text
        assert r1.exit_code == 0
        r2 = runner.invoke(app, ["rules-suggestions", "--format", "csv"])
        assert r2.exit_code == 0
