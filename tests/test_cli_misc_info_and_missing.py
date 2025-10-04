from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import mcp_rules_assistant.cli as cli


def test_cli_version_and_explain_and_start_and_install_hooks(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # ensure config exists for explain-performance
        r_init = runner.invoke(cli.app, ["init"])  # creates .mcp/assistant.yaml
        assert r_init.exit_code == 0
        # explain-performance
        r_exp = runner.invoke(cli.app, ["explain-performance"])
        assert r_exp.exit_code == 0
        assert "Performance Summary" in (r_exp.stdout or "")
        # version
        r_ver = runner.invoke(cli.app, ["version"])
        assert r_ver.exit_code == 0
        assert "mcp-rules-assistant" in (r_ver.stdout or "")
        # stub server.start to avoid blocking and cover CLI path
        called = {}

        def _fake_start():
            called["ok"] = True

        cli.server.start = _fake_start  # type: ignore[attr-defined]
        r_start = runner.invoke(cli.app, ["start"])
        assert r_start.exit_code == 0
        assert called.get("ok") is True
        # install-hooks creates files and prints summary
        r_hooks = runner.invoke(cli.app, ["install-hooks"])
        assert r_hooks.exit_code == 0
        assert Path(".pre-commit-config.yaml").exists()
        assert Path(".git/hooks/pre-push").exists()
        assert Path(".mcp/plan_gate.py").exists()


def test_cli_missing_resources_paths(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # rules-validate without ingest → exit 1
        r1 = runner.invoke(cli.app, ["rules-validate"])
        out1 = r1.stdout or ""
        assert r1.exit_code != 0 and ("尚未" in out1 or "no raw rules ingested" in out1)
        # rules-explain without file → exit 1
        r2 = runner.invoke(cli.app, ["rules-explain"])
        assert r2.exit_code != 0 and "尚未找到 .mcp/rules_compiled.json" in (
            r2.stdout or ""
        )
        # rules-suggestions without file → exit 1
        r3 = runner.invoke(cli.app, ["rules-suggestions"])
        assert r3.exit_code != 0 and "尚未找到 .mcp/rules_compiled.json" in (
            r3.stdout or ""
        )
        # coverage commands without coverage.xml → exit 1
        for cmd in ("coverage", "coverage-groups", "coverage-tree"):
            r = runner.invoke(cli.app, [cmd])
            assert r.exit_code != 0
            msg = r.stdout or ""
            assert ("coverage.xml 不存在" in msg) or ("coverage.xml not found" in msg)
