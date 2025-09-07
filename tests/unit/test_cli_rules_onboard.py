from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_rules_onboard_apply(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # run onboarding with apply (default)
        r = runner.invoke(
            app,
            [
                "rules-onboard",
                "--scenario",
                "personal",
                "--complexity",
                "small",
                "--dev-mode",
                "tdd",
            ],
        )
        assert r.exit_code == 0
        cfg = Path(".mcp/assistant.yaml")
        assert cfg.exists()
        text = cfg.read_text(encoding="utf-8")
        # personal+small → min_module=0.90, mutation_test false
        assert "min_module: 0.9" in text
        assert "mutation_test: false" in text


def test_cli_rules_onboard_dry_run(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        r = runner.invoke(
            app,
            [
                "rules-onboard",
                "--scenario",
                "enterprise",
                "--complexity",
                "large",
                "--dev-mode",
                "tdd",
                "--dry-run",
            ],
        )
        assert r.exit_code == 0
        # no file written
        assert not (tmp_path / ".mcp/assistant.yaml").exists()
        # output contains applied: False (rich prints single-quoted dict)
        assert "'applied': False" in (r.stdout or r.output)
