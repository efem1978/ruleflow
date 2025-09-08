from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_plan_shortcuts(tmp_path: Path) -> None:
    r = CliRunner()
    with r.isolated_filesystem(temp_dir=tmp_path):
        # init plan
        r.invoke(app, ["plan-init"])  # ensure exists
        r1 = r.invoke(app, ["plan-current", "编写代码"])
        assert r1.exit_code == 0
        r2 = r.invoke(app, ["plan-next", "编写测试"])
        assert r2.exit_code == 0
        text = Path(".mcp/plan.md").read_text(encoding="utf-8")
        assert "- 当前步骤: 编写代码" in text
        assert "- 下一步: 编写测试" in text
        r3 = r.invoke(app, ["plan-done"])  # mark done
        assert r3.exit_code == 0
        text2 = Path(".mcp/plan.md").read_text(encoding="utf-8")
        assert "- 状态: done" in text2


def test_cli_rules_export(tmp_path: Path) -> None:
    r = CliRunner()
    with r.isolated_filesystem(temp_dir=tmp_path):
        d = Path(".mcp")
        d.mkdir(parents=True, exist_ok=True)
        (d / "rules_compiled.json").write_text('{"policy":{}}', encoding="utf-8")
        (d / "rules_compiled.md").write_text("# Rules", encoding="utf-8")
        (d / "rules_suggestions.md").write_text("# Suggestions", encoding="utf-8")
        outd = tmp_path / "out"
        out = r.invoke(app, ["rules-export", "--out-dir", str(outd), "--format", "all"])
        assert out.exit_code == 0
        assert (outd / "rules_compiled.json").exists()
        assert (outd / "rules_compiled.md").exists()
        assert (outd / "rules_suggestions.md").exists()
