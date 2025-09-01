from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_plan_set_updates_file(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        r = runner.invoke(app, ["plan-set", "--status", "in_progress", "--current", "实现X", "--next-step", "Y"])
        assert r.exit_code == 0
        text = Path(".mcp/plan.md").read_text(encoding="utf-8")
        assert "- 状态:" in text and "in_progress" in text
        assert "- 当前步骤:" in text and "实现X" in text
        assert "- 下一步:" in text and "Y" in text


def test_cli_rules_validate_after_ingest(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        d = Path("r.md")
        d.write_text("- 覆盖率 90%\n- 禁止 skip/xfail\n", encoding="utf-8")
        r1 = runner.invoke(app, ["ingest-rules", str(d)])
        assert r1.exit_code == 0
        r2 = runner.invoke(app, ["rules-validate"])
        assert r2.exit_code == 0
        out = r2.stdout or ""
        assert "conflicts" in out and "suggestions" in out
