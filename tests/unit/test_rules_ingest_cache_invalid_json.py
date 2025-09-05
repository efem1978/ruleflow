from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_ingest_ignores_invalid_cache_json(tmp_path: Path) -> None:
    # write invalid cache json
    (tmp_path / '.mcp').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.mcp/rules_ingest_cache.json').write_text('{invalid', encoding='utf-8')
    p = tmp_path / 'd.md'
    p.write_text('- coverage 95%', encoding='utf-8')
    out = ri.ingest([str(p)], project_root=tmp_path)
    assert out.get('files') == 1 and (out.get('compiled') or {}).get('ok', True)

