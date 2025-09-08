from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_cleanup_removes_artifacts_and_handles_exceptions(
    tmp_path: Path, monkeypatch
) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create typical artifacts
        Path("coverage.xml").write_text('<coverage line-rate="1"/>', encoding="utf-8")
        Path(".coverage").write_text("data", encoding="utf-8")
        Path("cov.json").write_text("{}", encoding="utf-8")
        Path("cov.extra.json").write_text("{}", encoding="utf-8")
        Path("pytest-junit.xml").write_text("<testsuite/>", encoding="utf-8")
        (Path(".pytest_cache") / "dummy").parent.mkdir(parents=True, exist_ok=True)
        (Path("htmlcov") / "index.html").parent.mkdir(parents=True, exist_ok=True)
        # Run cleanup
        # Force one unlink failure to hit exception path
        original_unlink = Path.unlink

        def _boom(self, *a, **k):
            raise OSError("boom")

        monkeypatch.setattr(Path, "unlink", _boom)
        r = runner.invoke(app, ["cleanup"])  # default --artifacts
        # restore to allow assertions creating files later if needed
        monkeypatch.setattr(Path, "unlink", original_unlink)
        out = r.stdout or ""
        assert r.exit_code == 0
        # Files/dirs should be removed where possible; directories should be gone
        assert ".pytest_cache" in out or "htmlcov" in out
        assert not Path(".pytest_cache").exists()
        assert not Path("htmlcov").exists()


def test_cli_compliance_commitment_default_writes_to_mcp(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Run without --out, should write to .mcp/compliance.md (server writes, CLI ensures fallback)
        r = runner.invoke(app, ["compliance-commitment"])  # default write=True
        assert r.exit_code == 0
        p = Path(".mcp/compliance.md")
        assert p.exists() and p.read_text(encoding="utf-8").strip().startswith(
            "# AI 合规承诺"
        )


def test_cli_compliance_commitment_fallback_when_server_did_not_write(
    tmp_path: Path, monkeypatch
) -> None:
    # Monkeypatch JsonRpcServer to simulate not writing to disk
    import mcp_rules_assistant.cli as cli

    class DummySrv:
        def __init__(self) -> None:
            self.project_root = Path.cwd()

        def _call_tool(self, name: str, args: dict) -> dict:
            # return text but do not write any file
            return {
                "ok": True,
                "written": False,
                "text": "# AI 合规承诺 / AI Compliance Commitment",
            }

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        monkeypatch.setattr(cli, "JsonRpcServer", DummySrv)  # type: ignore[attr-defined]
        r = runner.invoke(cli.app, ["compliance-commitment"])  # no --out
        assert r.exit_code == 0
        # Fallback should have written .mcp/compliance.md
        assert (Path(".mcp/compliance.md")).exists()
