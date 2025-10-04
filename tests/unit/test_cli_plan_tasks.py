from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_plan_tasks_json_and_text(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        p = Path(".mcp/plan.md")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("- [x] A\n- [ ] B\n", encoding="utf-8")
        r1 = runner.invoke(app, ["plan-tasks", "--json"])
        assert r1.exit_code == 0
        data = json.loads(r1.stdout)
        assert data["counts"]["pending"] == 1 and data["counts"]["done"] == 1

        r2 = runner.invoke(app, ["plan-tasks", "--text"])
        assert r2.exit_code == 0
        assert "pending=1" in r2.stdout and "Done" in r2.stdout
