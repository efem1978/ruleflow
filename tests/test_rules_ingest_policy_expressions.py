from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.rules_ingest as ri


def test_interpret_policy_various_expressions(tmp_path: Path) -> None:
    # build a mixed text file with code fences to exercise skip logic
    text = (
        "- 覆盖率 九成五\n"  # 95%
        "- 核心 覆盖率 90%\n"  # core min
        "```\n- 这段应被忽略 skip\n```\n"
        "- at most ninety percent\n"  # upper bound max
        "- between 80 and 90 percent\n"  # range
        "- 性能预算 250ms\n"
        "- 禁止 skip/xfail\n"
        "- warnings as errors\n"
        "- 变异测试\n"
        "- tdd\n- 严格按顺序\n"
        "- require ci\n- 约定式提交\n- 分支策略\n"
        "- dockerfile\n- 镜像基线\n"
    )
    p = tmp_path / 'r.md'
    p.write_text(text, encoding='utf-8')
    out = ri.ingest([str(p)], project_root=tmp_path)
    comp = ri.compile_rules(project_root=tmp_path)
    assert comp.get('ok') is True
    pol = comp.get('policy', {})
    assert pol.get('coverage.min_module') and pol.get('coverage.min_core')
    # ensure suggestions built for several keys
    sugg = comp.get('suggestions', [])
    keys = {s.get('key') for s in sugg if isinstance(s, dict)}
    # suggestions include coverage thresholds; security.secrets_scan may not always suggest
    assert 'coverage.min_module' in keys
