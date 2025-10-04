from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app

runner = CliRunner()


def test_precommit_migrate_stages(tmp_path: Path, monkeypatch):
    # Arrange: legacy stages config
    cfg = tmp_path / ".pre-commit-config.yaml"
    cfg.write_text(
        """
repos:
  - repo: local
    hooks:
      - id: x
        stages: [commit, push]
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    # Act
    res = runner.invoke(app, ["precommit-migrate-stages"])

    # Assert
    assert res.exit_code == 0
    text = cfg.read_text(encoding="utf-8")
    assert "pre-commit" in text and "pre-push" in text


def test_license_hs256_roundtrip(tmp_path: Path, monkeypatch):
    # Redirect HOME for license path
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MCP_LICENSE_SALT", "test-salt")

    # Generate a license (hs256)
    res_gen = runner.invoke(
        app,
        [
            "license-generate",
            "--issued-to",
            "tester",
            "--expires",
            "2099-01-01",
            "--out",
            str(tmp_path / "lic.json"),
        ],
    )
    assert res_gen.exit_code == 0
    assert (tmp_path / "lic.json").exists()

    # Activate
    res_act = runner.invoke(
        app, ["license-activate", "--file", str(tmp_path / "lic.json")],
    )
    assert res_act.exit_code == 0

    # Verify
    res_ver = runner.invoke(app, ["license-verify"])
    assert res_ver.exit_code == 0
    data = json.loads(res_ver.stdout.strip())
    assert data.get("activated") is True


def test_rules_explain_json(tmp_path: Path, monkeypatch):
    # Provide a minimal compiled rules artifact
    dot = tmp_path / ".mcp"
    dot.mkdir(parents=True, exist_ok=True)
    compiled = {
        "policy": {"coverage.min_module": 0.9, "security.secrets_scan": True},
        "conflicts": [],
        "suggestions": [],
        "meta": {"maxima": {"coverage.max_module": 0.01, "coverage.max_core": 0.97}},
    }
    (dot / "rules_compiled.json").write_text(json.dumps(compiled), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    res = runner.invoke(app, ["rules-explain", "--json"])
    assert res.exit_code == 0
    out = json.loads(res.stdout.strip())
    assert out["coverage"]["min_module"] == 0.9


def test_coverage_near_set(tmp_path: Path, monkeypatch):
    # Ensure assistant.yaml exists to be updated
    dot = tmp_path / ".mcp"
    dot.mkdir(parents=True, exist_ok=True)
    (dot / "assistant.yaml").write_text(
        "performance:\n  on_push:\n    coverage:\n      min_module: 0.9\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    res = runner.invoke(app, ["coverage-near-set", "--within", "5", "--top", "10"])
    assert res.exit_code == 0
    text = (dot / "assistant.yaml").read_text(encoding="utf-8")
    assert "within" in text and "top" in text
