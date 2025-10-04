from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_diagnose_json(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".mcp").mkdir(parents=True, exist_ok=True)
        Path(".mcp/assistant.yaml").write_text(
            "performance:\n  on_push:\n    coverage: {min_module: 0.90}\n",
            encoding="utf-8",
        )
        r = runner.invoke(app, ["diagnose", "--json"])
        assert r.exit_code == 0
        data = json.loads(r.stdout or "{}")
        assert "python_version" in data and "tools" in data and "config" in data
        assert "min_module" in (data.get("config") or {})
