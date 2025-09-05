from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.config import (
    default_config_dict,
    ensure_project_config,
    load_config,
    human_summary,
)


def test_ensure_and_load_defaults(tmp_path: Path) -> None:
    cfg_path = tmp_path / ".mcp" / "assistant.yaml"
    ensure_project_config(cfg_path)
    assert cfg_path.exists()

    cfg = load_config(project_path=tmp_path)
    d = default_config_dict()
    # sanity: default keys merged
    assert cfg.get("performance", {}).get("mode") == d["performance"]["mode"]
    # coverage policy defaults present
    cov = cfg["performance"]["on_push"]["coverage"]
    assert cov["enforce"] is True and cov["min_module"] == 0.9


def test_human_summary_contains_key_sections(tmp_path: Path) -> None:
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/assistant.yaml").write_text("""
performance:
  mode: fast
  on_save:
    format_on_save: true
    lint_changed_only: true
    typecheck_incremental: false
    quick_tests: false
  on_commit:
    lint: true
    typecheck_incremental: true
    test_impacted: true
  on_push:
    test_all: true
    coverage: { enforce: true, min_module: 0.95, min_core: 0.98 }
    security_scan: true
    mutation_test: false
""", encoding="utf-8")
    cfg = load_config(project_path=tmp_path)
    s = human_summary(cfg)
    assert "Mode:" in s and "On Save:" in s and "On Push:" in s
    assert "min_module=0.95" in s

