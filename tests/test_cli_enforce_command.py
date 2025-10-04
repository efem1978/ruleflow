from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_enforce_outputs_enforced_and_next(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # prepare compiled rules in current CWD
        mp = Path(".mcp")
        mp.mkdir(parents=True, exist_ok=True)
        (mp / "rules_compiled.json").write_text(
            '{"policy": {"coverage.min_module": 0.9, "security.sast_strict": true}}',
            encoding="utf-8",
        )
        r = runner.invoke(app, ["enforce"])
        assert r.exit_code == 0
        out = r.stdout or ""
        assert "Enforced gates" in out
        assert "Next" in out and "install-hooks" in out
