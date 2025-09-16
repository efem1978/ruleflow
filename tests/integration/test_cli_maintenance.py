from __future__ import annotations

import os
from pathlib import Path

from mcp_rules_assistant import cli


def test_cli_maintenance_creates_hooks_and_ci(tmp_path: Path, capsys) -> None:
    # prepare a fake git repo structure
    (tmp_path / ".git" / "hooks").mkdir(parents=True, exist_ok=True)
    cwd = os.getcwd()
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
