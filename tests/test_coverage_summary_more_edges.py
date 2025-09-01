from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.coverage_summary as cs


def test_read_classes_with_cache_read_bytes_exception(monkeypatch, tmp_path: Path) -> None:
    cov = tmp_path / 'coverage.xml'
    cov.write_text('<coverage><packages><package><classes></classes></package></packages></coverage>', encoding='utf-8')
    import pathlib
    orig = pathlib.Path.read_bytes
    def bad_read(self):
        if self == cov.resolve():
            raise OSError('boom')
        return orig(self)
    monkeypatch.setattr(pathlib.Path, 'read_bytes', bad_read)
    r = cs.summarize(project_root=tmp_path)
    assert r.get('ok') is True


def test_parse_invalid_xml_returns_empty(tmp_path: Path) -> None:
    cov = tmp_path / 'coverage.xml'
    cov.write_text('<not-xml>', encoding='utf-8')
    # summarize should handle parse error gracefully (items=[]) and still ok True
    r = cs.summarize(project_root=tmp_path)
    assert r.get('ok') is True and isinstance(r.get('weak'), list)
    # invalid cache JSON path
    (tmp_path / '.mcp').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.mcp/coverage_cache.json').write_text('{invalid', encoding='utf-8')
    cov2 = tmp_path / 'coverage2.xml'
    cov2.write_text('<coverage><packages><package><classes></classes></package></packages></coverage>', encoding='utf-8')
    r2 = cs.summarize(project_root=tmp_path, coverage_xml='coverage2.xml')
    assert r2.get('ok') is True
    # files not dict
    (tmp_path / '.mcp/coverage_cache.json').write_text('{"files": []}', encoding='utf-8')
    r3 = cs.summarize(project_root=tmp_path, coverage_xml='coverage2.xml')
    assert r3.get('ok') is True


def test_read_classes_hash_exception(monkeypatch, tmp_path: Path) -> None:
    cov = tmp_path / 'cov.xml'
    cov.write_text('<coverage></coverage>', encoding='utf-8')
    class Bad:
        def __init__(self, *a, **k):
            pass
        def update(self, *a, **k):
            raise OSError('x')
        def hexdigest(self):
            return '0'
    monkeypatch.setattr(cs, 'hashlib', type('H', (), {'sha1': lambda *a, **k: Bad() }))
    items = cs._read_classes_with_cache(tmp_path, 'cov.xml')
    assert isinstance(items, list)


def test_cache_write_exception(monkeypatch, tmp_path: Path) -> None:
    cov = tmp_path / 'coverage.xml'
    cov.write_text('<coverage><packages><package><classes></classes></package></packages></coverage>', encoding='utf-8')
    import pathlib
    orig = pathlib.Path.write_text
    def bad_write(self, *a, **k):
        if str(self).endswith('coverage_cache.json'):
            raise OSError('nope')
        return orig(self, *a, **k)
    monkeypatch.setattr(pathlib.Path, 'write_text', bad_write)
    r = cs.summarize(project_root=tmp_path)
    assert r.get('ok') is True


def test_read_classes_nonexistent_path(tmp_path: Path) -> None:
    items = cs._read_classes_with_cache(tmp_path, 'no-such.xml')
    assert items == []


def test_read_classes_hash_exception(monkeypatch, tmp_path: Path) -> None:
    cov = tmp_path / 'cov.xml'
    cov.write_text('<coverage></coverage>', encoding='utf-8')
    class Bad:
        def __init__(self, *a, **k):
            pass
        def update(self, *a, **k):
            raise OSError('x')
        def hexdigest(self):
            return '0'
    import types, sys
    def raise_sha1(*a, **k):
        raise OSError('sha1boom')
    fake_hashlib = types.SimpleNamespace(sha1=raise_sha1)
    monkeypatch.setitem(sys.modules, 'hashlib', fake_hashlib)
    items = cs._read_classes_with_cache(tmp_path, 'cov.xml')
    assert isinstance(items, list)


def test_lines_valid_covered_value_error(tmp_path: Path) -> None:
    cov = tmp_path / 'coverage.xml'
    cov.write_text(
        '<coverage><packages><package><classes>'
        '<class filename="a.py" lines-valid="x" lines-covered="y"/>'
        '</classes></package></packages></coverage>', encoding='utf-8')
    r = cs.summarize(project_root=tmp_path)
    assert r.get('ok') is True
