from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_yaml_nested_flattens_to_coverage_keys(tmp_path: Path) -> None:
    y = tmp_path / "r.yaml"
    y.write_text("coverage:\n  min_module: 0.93\n  min_core: 0.98\n", encoding="utf-8")
    out = ri.ingest([str(y)], project_root=tmp_path)
    pol = (out.get("compiled") or {}).get("policy") or {}
    assert abs(float(pol.get("coverage.min_module")) - 0.93) < 1e-6
    assert abs(float(pol.get("coverage.min_core")) - 0.98) < 1e-6
