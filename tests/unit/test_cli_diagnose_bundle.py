from __future__ import annotations

import tarfile
from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_diagnose_bundle_creates_archive(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Prepare minimal artifacts
        Path("coverage.xml").write_text('<coverage line-rate="1"/>', encoding="utf-8")
        Path("pytest-junit.xml").write_text("<testsuite/>", encoding="utf-8")
        Path("near.json").write_text("[]", encoding="utf-8")
        (Path(".mcp") / "dashboard").mkdir(parents=True, exist_ok=True)
        Path(".mcp/assistant.yaml").write_text("language: python\n", encoding="utf-8")
        Path(".mcp/plan.md").write_text(
            "- 状态: in_progress\n- 当前步骤: x\n", encoding="utf-8"
        )
        Path(".mcp/memory.json").write_text("{}", encoding="utf-8")
        Path(".mcp/rules_compiled.json").write_text("{}", encoding="utf-8")
        Path(".mcp/rules_compiled.md").write_text("# rules\n", encoding="utf-8")
        Path(".mcp/rules_suggestions.md").write_text("# sugg\n", encoding="utf-8")
        Path(".mcp/rules_raw.json").write_text("{}", encoding="utf-8")
        Path(".mcp/dashboard/status.json").write_text("{}", encoding="utf-8")
        Path(".mcp/dashboard/history.json").write_text("[]", encoding="utf-8")

        # Run command
        r = runner.invoke(app, ["diagnose-bundle"])  # default output path
        assert r.exit_code == 0
        # Find produced tarball
        tars = list(Path.cwd().glob("diagnostics-*.tar.gz"))
        assert len(tars) == 1
        tar_path = tars[0]
        # Inspect archive members
        with tarfile.open(tar_path, mode="r:gz") as tar:
            names = set(m.name for m in tar.getmembers())
        # A few sample entries should be present
        assert "coverage.xml" in names
        assert ".mcp/assistant.yaml" in names
        assert ".mcp/dashboard/history.json" in names
