from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_ingest_empty_yaml_and_json(tmp_path: Path) -> None:
    y = tmp_path / 'empty.yaml'; y.write_text('', encoding='utf-8')
    j = tmp_path / 'empty.json'; j.write_text('{}', encoding='utf-8')
    out = ri.ingest([str(y), str(j)], project_root=tmp_path)
    assert out.get('files') == 2
    assert isinstance(out.get('compiled'), dict)
    # 空文档不应产生有效策略键（允许空键占位）
    pol = (out.get('compiled') or {}).get('policy') or {}
    assert pol == {} or (set(pol.keys()) == {''} and pol.get('') is None)
