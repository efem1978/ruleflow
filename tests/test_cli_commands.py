from __future__ import annotations

import os
from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def chdir(path: Path):
    class _Ctx:
        def __enter__(self):
            self._old = Path.cwd()
            os.chdir(path)
            return path

        def __exit__(self, exc_type, exc, tb):
            os.chdir(self._old)

    return _Ctx()


def _write_cov_xml(path: Path) -> None:
    text = (
        "<coverage>\n"
        "  <packages><package><classes>\n"
        '    <class filename="mcp_rules_assistant/foo.py" line-rate="0.91" lines-valid="100" lines-covered="91"/>\n'
        '    <class filename="other/bar.py" line-rate="0.88" lines-valid="100" lines-covered="88"/>\n'
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    path.write_text(text, encoding="utf-8")


def test_cli_init_print_and_plan(tmp_path: Path) -> None:
    runner = CliRunner()
    with chdir(tmp_path):
        # init
        r = runner.invoke(app, ["init"])
        assert r.exit_code == 0
        assert (tmp_path / ".mcp/assistant.yaml").exists()
        # print-config
        r2 = runner.invoke(app, ["print-config"])
        assert r2.exit_code == 0
        assert "performance" in (r2.stdout or "")
        # plan init/open/update
        r3 = runner.invoke(app, ["plan-init"])
        assert r3.exit_code == 0
        plan = tmp_path / ".mcp/plan.md"
        assert plan.exists()
        r4 = runner.invoke(
            app,
            [
                "plan-update",
                "# 计划\n- 状态: in_progress\n- 当前步骤: CLI 烟雾测试\n- 下一步: 生成 CI\n",
            ],
        )
        assert r4.exit_code == 0
        r5 = runner.invoke(app, ["plan-open"])
        assert r5.exit_code == 0
        assert "CLI 烟雾测试" in (r5.stdout or "")


def test_cli_ci_set_and_generate_ci(tmp_path: Path) -> None:
    runner = CliRunner()
    with chdir(tmp_path):
        # enable hadolint/semgrep in config
        r = runner.invoke(
            app,
            [
                "ci-set",
                "--hadolint",
                "--semgrep-config",
                "p/ci",
                "--hadolint-image",
                "hadolint/hadolint:latest",
                "--hadolint-args",
                "--ignore DL3008",
            ],
        )
        assert r.exit_code == 0
        # compiled rules enabling container and sast strict → CI should include extra steps
        compiled = tmp_path / ".mcp/rules_compiled.json"
        compiled.parent.mkdir(parents=True, exist_ok=True)
        compiled.write_text(
            "{" '"policy": {"container.required": true, "security.sast_strict": true}}',
            encoding="utf-8",
        )
        # generate CI
        r2 = runner.invoke(app, ["generate-ci"])
        assert r2.exit_code == 0
        yml = (tmp_path / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        assert "Check Dockerfile existence" in yml
        assert "SAST (semgrep)" in yml
        # hadolint step included only when container is relevant and hadolint enabled
        assert "Dockerfile Lint (hadolint)" in yml


def test_cli_rules_ingest_and_coverage_outputs(tmp_path: Path) -> None:
    runner = CliRunner()
    with chdir(tmp_path):
        # prepare a rules doc and ingest
        d = tmp_path / "r.md"
        d.write_text("- 覆盖率 90%\n- 禁止 skip/xfail\n", encoding="utf-8")
        r = runner.invoke(app, ["ingest-rules", str(d)])
        assert r.exit_code == 0
        assert (tmp_path / ".mcp/rules_compiled.json").exists()
        # prepare coverage.xml and print coverage summaries
        _write_cov_xml(tmp_path / "coverage.xml")
        rc = runner.invoke(app, ["coverage"])
        assert rc.exit_code == 0
        assert "覆盖率薄弱文件" in (rc.stdout or "")
        rg = runner.invoke(app, ["coverage-groups"])
        assert rg.exit_code == 0
        assert "覆盖率分组" in (rg.stdout or "")
