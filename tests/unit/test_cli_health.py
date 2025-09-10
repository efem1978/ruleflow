from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_health_json(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Ensure minimal workspace; health should create plan if missing
        r = runner.invoke(app, ["health", "--json"])
        assert r.exit_code == 0
        out = r.stdout or ""
        assert "coverage" in out and "plan" in out and "status_ok" in out


def test_cli_health_text(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create minimal plan to exercise plan task counting and text branch
        p = Path(".mcp/plan.md")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "# 计划\n- 状态: in_progress\n- 当前步骤: t\n- 下一步: n\n- [ ] a\n- [x] b\n",
            encoding="utf-8",
        )
        r = runner.invoke(app, ["health", "--text"])
        assert r.exit_code == 0
        out = r.stdout or ""
        assert "Health" in out and "compiled_rules=" in out and "coverage.xml=" in out
