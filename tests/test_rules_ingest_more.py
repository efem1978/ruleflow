from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri
from mcp_rules_assistant.hooks import generate_pre_commit_config


def test_extract_warnings_as_errors_and_suggestion(tmp_path: Path) -> None:
    d = tmp_path / "w.md"
    d.write_text("- 警告视为错误\n", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert pol.get("test.warnings_as_errors") is True
    sugg = (res.get("compiled") or {}).get("suggestions") or []
    assert any(
        s.get("key") == "test.warnings_as_errors" and s.get("action") == "enforce"
        for s in sugg
    )


def test_extract_perf_budget_ms(tmp_path: Path) -> None:
    d = tmp_path / "p.md"
    d.write_text("- 性能预算 不低于 200ms\n", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert int(pol.get("perf.budget_ms") or 0) == 200


def test_pre_commit_contains_docker_baseline_hook_when_policy_enabled(
    tmp_path: Path,
) -> None:
    # Seed compiled rules to enable container baseline
    comp = tmp_path / ".mcp/rules_compiled.json"
    comp.parent.mkdir(parents=True, exist_ok=True)
    comp.write_text('{"policy": {"container.policy.baseline": true}}', encoding="utf-8")
    cfg = generate_pre_commit_config(tmp_path)
    text = cfg.read_text(encoding="utf-8")
    assert "dockerfile-baseline" in text and "stages: [push]" in text


def test_core_threshold_via_phrase_without_percent(tmp_path: Path) -> None:
    d = tmp_path / "core.md"
    d.write_text("- 核心 不少于 96\n", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_core")) - 0.96) < 1e-6
