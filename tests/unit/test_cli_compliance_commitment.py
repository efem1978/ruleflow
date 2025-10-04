from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_compliance_commitment_write(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        outp = str(tmp_path / "COMMITMENT.md")
        r = runner.invoke(app, ["compliance-commitment", "--out", outp])
        assert r.exit_code == 0
        p = Path(outp)
        assert p.exists()
        assert "AI 合规承诺" in p.read_text(encoding="utf-8")
