from __future__ import annotations

from pathlib import Path
import os
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


def test_cli_ci_validate_and_autofix(tmp_path: Path) -> None:
    runner = CliRunner()
    with chdir(tmp_path):
        # generate-ci first
        rgen = runner.invoke(app, ["generate-ci"])
        assert rgen.exit_code == 0
        # validate
        rval = runner.invoke(app, ["ci-validate"])
        assert rval.exit_code == 0
        out = rval.stdout or ""
        assert "exists" in out and "has_tests" in out
        # perturb ci.yml then autofix
        ci = tmp_path / ".github/workflows/ci.yml"
        ci.write_text("name: bad\n", encoding="utf-8")
        rfix = runner.invoke(app, ["ci-autofix"])
        assert rfix.exit_code == 0
        # backup path should be reported when changed
        assert "backup" in (rfix.stdout or "")
