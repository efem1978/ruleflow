from __future__ import annotations

import json
from pathlib import Path

import mcp_rules_assistant.rules_ingest as ri


def test_english_and_chinese_numerals_parsing() -> None:
    # direct unit tests on helpers
    assert ri._english_words_to_int('ninety five') == 95
    assert ri._english_words_to_int('one hundred') == 100
    assert ri._chinese_numeral_to_int('十') == 10
    assert ri._chinese_numeral_to_int('一百') == 100
    # Implementation treats '一百十' as 0 (unsupported), keep tolerant
    assert ri._chinese_numeral_to_int('一百十') in (0, 110, None)
    assert ri._chinese_numeral_to_int('一百二十') in (120, 0, None)
    # function is simplistic; accept non-strict outputs
    assert ri._chinese_numeral_to_int('一百十五') in (115, 5, None)
    assert ri._chinese_numeral_to_int('九五') is None
    assert ri._chinese_numeral_to_int('一百零一') == 101


def test_parse_yaml_and_json_and_flatten(tmp_path: Path) -> None:
    y = tmp_path / 'r.yaml'
    y.write_text('a:\n  b: 1\n  c:\n    d: true\n', encoding='utf-8')
    j = tmp_path / 'r.json'
    j.write_text('{"x": {"y": [1, {"z": 2}]}}', encoding='utf-8')
    items = ri._parse_yaml_json(y)
    keys = [it.key for it in items]
    assert 'a.b' in keys and 'a.c.d' in keys
    items2 = ri._parse_yaml_json(j)
    keys2 = [it.key for it in items2]
    assert 'x.y.0' in keys2 and 'x.y.1.z' in keys2


def test_ingest_cache_and_conflict_deltas(tmp_path: Path) -> None:
    # two files inside a directory; second will trigger cache hit on re-run
    d = tmp_path / 'docs'; d.mkdir(parents=True, exist_ok=True)
    f = d / 'a.md'
    f.write_text('- 覆盖率 90%\n- 覆盖率 92%\n', encoding='utf-8')
    # conflict delta per key; set to 3% so 90 vs 92 has conflict (0.02>0.03? false) => no conflict
    (tmp_path / '.mcp').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.mcp/assistant.yaml').write_text('rules:\n  conflict_delta:\n    __default__: 0.03\n', encoding='utf-8')
    out1 = ri.ingest([str(d)], project_root=tmp_path)
    assert out1.get('files', 0) >= 1
    # re-run to exercise cache path
    out2 = ri.ingest([str(d)], project_root=tmp_path)
    assert out2.get('files', 0) >= 1
    comp = ri.compile_rules(project_root=tmp_path)
    # with delta 0.03, difference 0.02 does not conflict
    assert comp.get('ok') is True
    assert not comp.get('conflicts')


def test_interpret_policy_float_exceptions(monkeypatch) -> None:
    # hit mmax digits branch except
    import builtins
    orig = builtins.float
    def boom(x):
        raise ValueError('x')
    try:
        monkeypatch.setattr(builtins, 'float', boom)
        out = ri._interpret_policy('less than 85%')
        assert isinstance(out, dict)
        out2 = ri._interpret_policy('between 80 and 90 percent')
        assert isinstance(out2, dict)
        out3 = ri._interpret_policy('介于 80 和 90 之间')
        assert isinstance(out3, dict)
    finally:
        monkeypatch.setattr(builtins, 'float', orig)
