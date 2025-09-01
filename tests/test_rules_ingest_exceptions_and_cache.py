from __future__ import annotations

from pathlib import Path
import types

import mcp_rules_assistant.rules_ingest as ri


def test_parse_text_file_read_error() -> None:
    class Bad:
        def read_text(self, *a, **k):
            raise OSError('boom')
        def __str__(self):
            return 'bad'
    items = ri._parse_text_file(Bad())  # type: ignore[arg-type]
    assert items == []


def test_extract_percentage_exception_paths(monkeypatch) -> None:
    # temporarily poison float() to throw to reach except branches
    import builtins
    orig_float = builtins.float
    def bad_float(x):
        raise ValueError('bad')
    try:
        monkeypatch.setattr(builtins, 'float', bad_float)
        assert ri._extract_percentage('95%') is None
        assert ri._extract_percentage('at least 90') is None
        assert ri._extract_percentage('95 percent') is None
    finally:
        monkeypatch.setattr(builtins, 'float', orig_float)


def test_parse_yaml_json_invalid(tmp_path: Path) -> None:
    bad = tmp_path / 'x.json'
    bad.write_text('{invalid', encoding='utf-8')
    items = ri._parse_yaml_json(bad)
    assert items == []


def test_compile_rules_invalid_config_yaml(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / '.mcp').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.mcp/rules_raw.json').write_text('{"items": [], "files": []}', encoding='utf-8')
    import yaml
    def boom(*a, **k):
        raise yaml.YAMLError('bad')
    monkeypatch.setattr(yaml, 'safe_load', boom)
    out = ri.compile_rules(project_root=tmp_path)
    assert out.get('ok') is True


def test_ingest_cache_write_exception(monkeypatch, tmp_path: Path) -> None:
    d = tmp_path / 'docs'; d.mkdir(parents=True, exist_ok=True)
    (d / 'a.md').write_text('- 覆盖率 90%\n', encoding='utf-8')
    import pathlib
    orig_write = pathlib.Path.write_text
    def bad_write(self, *a, **k):
        if str(self).endswith('rules_ingest_cache.json'):
            raise OSError('nope')
        return orig_write(self, *a, **k)
    monkeypatch.setattr(pathlib.Path, 'write_text', bad_write)
    out = ri.ingest([str(d)], project_root=tmp_path)
    assert out.get('files') >= 1
