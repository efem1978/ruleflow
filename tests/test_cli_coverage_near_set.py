from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from mcp_rules_assistant.cli import app
from mcp_rules_assistant.config import ensure_project_config


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


def test_cli_coverage_near_set_updates_config(tmp_path: Path) -> None:
    runner = CliRunner()
    with chdir(tmp_path):
        ensure_project_config()
        r = runner.invoke(app, ["coverage-near-set", "--within", "5", "--top", "10"])
        assert r.exit_code == 0
        y = (
            yaml.safe_load(
                (tmp_path / ".mcp/assistant.yaml").read_text(encoding="utf-8"),
            )
            or {}
        )
        near = (y.get("coverage", {}) or {}).get("near", {})
        assert abs(float(near.get("within")) - 0.05) < 1e-6
        assert int(near.get("top")) == 10
