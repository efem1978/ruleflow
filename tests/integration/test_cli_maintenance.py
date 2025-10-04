from __future__ import annotations

import os
from pathlib import Path

from mcp_rules_assistant import cli


def _safe_getcwd() -> str:
    try:
        return os.getcwd()
    except (FileNotFoundError, OSError):
        # Fall back to project root if current directory was removed by a previous test
        return str(Path(__file__).resolve().parent.parent.parent)


def test_cli_maintenance_creates_hooks_and_ci(tmp_path: Path, capsys) -> None:
    # prepare a fake git repo structure
    (tmp_path / ".git" / "hooks").mkdir(parents=True, exist_ok=True)
    cwd = _safe_getcwd()
    try:
        os.chdir(str(tmp_path))
        cli.maintenance()
        # hooks and ci should be written
        assert (tmp_path / ".git" / "hooks" / "pre-push").exists()
        assert (tmp_path / ".github" / "workflows" / "ci.yml").exists()
        out = capsys.readouterr().out
        assert "Maintenance completed" in out
    finally:
        try:
            os.chdir(cwd)
        except (FileNotFoundError, OSError):
            # If original directory was deleted, just continue
            pass
