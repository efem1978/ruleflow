from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def chdir(path: Path):
    class _Ctx:
        def __enter__(self):
            self._old = Path.cwd()
            import os
            os.chdir(path)
            return path

        def __exit__(self, exc_type, exc, tb):
            import os
            os.chdir(self._old)

    return _Ctx()


def test_ci_vscode_required_removes_if_condition(tmp_path: Path) -> None:
    runner = CliRunner()
    with chdir(tmp_path):
        r = runner.invoke(app, [
            "ci-set",
            "--vscode-required",
        ])
        assert r.exit_code == 0
        r2 = runner.invoke(app, ["generate-ci"])
        assert r2.exit_code == 0
        yml = (tmp_path / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        # When required, the conditional 'if: hashFiles(...)' should be absent
        assert "if: ${{ hashFiles('extensions/vscode/package.json') != '' }}" not in yml
        assert "VS Code extension tests" in yml

