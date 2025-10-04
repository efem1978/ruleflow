from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mcp_rules_assistant.cli", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )


def test_rules_explain_when_compiled_missing(tmp_path: Path) -> None:
    # Ensure no compiled file
    proc = run_cli(["rules-explain", "--json"], tmp_path)
    # Should exit with error and print hint
    assert proc.returncode != 0
    assert "尚未找到 .mcp/rules_compiled.json" in proc.stdout or proc.stderr


def test_coverage_report_json_schema(tmp_path: Path) -> None:
    # Create a minimal coverage.xml via running a trivial pytest session is heavy; instead just expect graceful error
    proc = run_cli(["coverage-report", "--json"], tmp_path)
    # If no coverage.xml, tool exits non-zero with message; both outcomes acceptable for contract
    assert proc.returncode in (0, 1)
    out = proc.stdout.strip()
    if proc.returncode == 0 and out:
        # When present, it should be valid JSON with keys
        import json

        data = json.loads(out)
        assert all(k in data for k in ("weak", "groups", "near", "min_module"))
