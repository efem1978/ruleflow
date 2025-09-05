from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_between_english_module(tmp_path: Path) -> None:
    d = tmp_path / 'bt1.md'
    d.write_text('- between 90% and 95% coverage', encoding='utf-8')
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get('compiled') or {}).get('policy') or {}
    assert abs(float(pol.get('coverage.min_module')) - 0.90) < 1e-6
    sugg = (res.get('compiled') or {}).get('suggestions') or []
    assert any((s.get('key') == 'coverage.max_module' and s.get('action') == 'monitor') for s in sugg)


def test_between_chinese_core(tmp_path: Path) -> None:
    d = tmp_path / 'bt2.md'
    d.write_text('- 核心 覆盖率 介于 96% 和 99% 之间', encoding='utf-8')
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get('compiled') or {}).get('policy') or {}
    assert abs(float(pol.get('coverage.min_core')) - 0.96) < 1e-6
    sugg = (res.get('compiled') or {}).get('suggestions') or []
    assert any((s.get('key') == 'coverage.max_core' and s.get('action') == 'monitor') for s in sugg)


def test_between_chinese_module(tmp_path: Path) -> None:
    """覆盖中文“介于 … 和 … 之间”模块级区间解析（无“核心”关键词）。"""
    d = tmp_path / 'bt3.md'
    d.write_text('- 覆盖率 介于 90% 和 95% 之间', encoding='utf-8')
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get('compiled') or {}).get('policy') or {}
    assert abs(float(pol.get('coverage.min_module')) - 0.90) < 1e-6
    sugg = (res.get('compiled') or {}).get('suggestions') or []
    # 应记录上限为 monitor 建议（不作门禁）
    assert any((s.get('key') == 'coverage.max_module' and s.get('action') == 'monitor') for s in sugg)
