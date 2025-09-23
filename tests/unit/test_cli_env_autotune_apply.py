from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def test_cli_env_autotune_json_and_apply(tmp_path: Path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    # Create a minimal workspace; ensure .mcp/assistant.yaml will be generated
    (tmp_path / "README.md").write_text("# readme", encoding="utf-8")
    # Create a Dockerfile to exercise dockerfile_exists branch (docker may be absent; it's fine)
    (tmp_path / "Dockerfile").write_text("FROM scratch", encoding="utf-8")

    # Dry-run mode prints JSON by默认（未 --apply）
    res_json = runner.invoke(app, ["env-autotune"])  # type: ignore[arg-type]
    assert res_json.exit_code == 0
    out = (res_json.stdout or "").strip()
    # Validate JSON structure
    payload = json.loads(out)
    assert isinstance(payload, dict)

    # Apply mode (should persist at least ci.vscode_required=false when code cli is not present)
    res_apply = runner.invoke(app, ["env-autotune", "--apply"])  # type: ignore[arg-type]
    assert res_apply.exit_code == 0
    # Verify assistant.yaml exists and contains a ci section (best-effort)
    cfg = tmp_path / ".mcp" / "assistant.yaml"
    assert cfg.exists()
    text = cfg.read_text(encoding="utf-8")
    assert "ci:" in text or "vscode_required" in text
