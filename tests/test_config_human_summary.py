from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.config import ensure_project_config, human_summary, load_config


def test_config_human_summary(tmp_path: Path) -> None:
    ensure_project_config(tmp_path / ".mcp/assistant.yaml")
    cfg = load_config(tmp_path)
    text = human_summary(cfg)
    assert "Mode:" in text and "On Save:" in text and "On Push:" in text
    # contains coverage thresholds from defaults
    assert "min_module=0.9" in text or "min_module=0.90" in text
