from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_numeric_percent_over_100_is_capped(tmp_path: Path) -> None:
    d = tmp_path / 'over.md'
    d.write_text('- 覆盖率 105%', encoding='utf-8')
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get('compiled') or {}).get('policy') or {}
    assert abs(float(pol.get('coverage.min_module')) - 1.0) < 1e-6

