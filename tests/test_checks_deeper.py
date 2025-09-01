from __future__ import annotations

import json
import time
from pathlib import Path

import mcp_rules_assistant.checks as checks


def test_run_type_and_lint_file_not_found(monkeypatch, tmp_path: Path) -> None:
    def boom(cmd, cwd=None, stdout=None, stderr=None, text=None, env=None):
        raise FileNotFoundError('nope')
    monkeypatch.setattr(checks.subprocess, 'run', boom)
    r1 = checks.run_typecheck(tmp_path)
    r2 = checks.run_lint([tmp_path / 'x.py'], tmp_path)
    assert r1.get('skipped') and r2.get('skipped')


def test_quick_tests_fallback_import_and_events_and_decay(tmp_path: Path, monkeypatch) -> None:
    # write config overriding decay to make both branches active
    (tmp_path / '.mcp').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.mcp/assistant.yaml').write_text(
        'tests:\n  quick_fail_decay: {high_days: 3, high_bonus: 2, mid_days: 7, mid_bonus: 1, history_limit: 2}\n',
        encoding='utf-8'
    )
    # write last_failed with recent and mid events to build bonus maps
    now = time.time()
    last = {
        'tests': [],
        'nodeids': [],
        'test_counts': {},
        'node_counts': {},
        'events': [
            {'nodeid': 'tests/test_a.py::test_a', 'file': str((tmp_path/'tests/test_a.py').resolve()), 'ts': str(now - 3600)},
            {'nodeid': 'tests/test_b.py::test_b', 'file': str((tmp_path/'tests/test_b.py').resolve()), 'ts': str(now - 5*24*3600)},
        ],
    }
    (tmp_path / '.mcp/last_failed_tests.json').write_text(json.dumps(last), encoding='utf-8')
    # create tests dir with fallback string imports (not real import statements) to exercise _discover_tests_by_import
    tdir = tmp_path / 'tests'; tdir.mkdir(parents=True, exist_ok=True)
    (tdir / 'test_any.py').write_text('x = "from pkg.mod import x"\n', encoding='utf-8')
    # create source file that maps to mod
    src = tmp_path / 'pkg/mod.py'; src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text('def f(): return 1\n', encoding='utf-8')
    # monkeypatch pytest run to simulate failed output; capture env PYTHONPATH injection indirectly
    def fake_run(cmd, cwd=None, env=None):
        # must include the discovered test path
        assert any(str((tmp_path/'tests/test_any.py')) in c for c in cmd if isinstance(c, str))
        return {"ok": False, "code": 1, "stdout": 'FAILED tests/test_mod.py::test_x - AssertionError\n', "stderr": '', "cmd": cmd}
    monkeypatch.setattr(checks, '_run', fake_run)
    res = checks.run_quick_tests([src], cwd=tmp_path)
    assert res.get('ok') is False
    # ensure last_failed updated
    data = json.loads((tmp_path / '.mcp/last_failed_tests.json').read_text(encoding='utf-8'))
    assert data.get('tests')


def test_build_index_parse_from_and_import_lines(tmp_path: Path) -> None:
    tdir = tmp_path / 'tests'; tdir.mkdir(parents=True, exist_ok=True)
    content = (
        'from pkg.alpha import a\n'
        'import pkg.beta\n'
        'print("done")\n'
    )
    (tdir / 'test_parse.py').write_text(content, encoding='utf-8')
    idx = checks.build_test_index(tmp_path)
    # both alpha and pkg.beta appear as keys
    assert 'pkg.alpha' in idx or 'pkg' in idx


def test_discover_tests_by_import_read_text_error(monkeypatch, tmp_path: Path) -> None:
    tdir = tmp_path / 'tests'; tdir.mkdir(parents=True, exist_ok=True)
    bad = tdir / 'test_err.py'
    bad.write_text('import x\n', encoding='utf-8')
    import pathlib
    orig = pathlib.Path.read_text
    def bad_read(self, *a, **k):
        if self == bad:
            raise OSError('nope')
        return orig(self, *a, **k)
    monkeypatch.setattr(pathlib.Path, 'read_text', bad_read)
    out = checks._discover_tests_by_import(tmp_path, ['x'])
    assert isinstance(out, set)


def test_load_test_index_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / '.mcp/test_index.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{invalid', encoding='utf-8')
    idx = checks.load_test_index(tmp_path)
    assert idx == {}


def test_index_meta_read_write_exceptions(monkeypatch, tmp_path: Path) -> None:
    # force _write_index_meta exception path
    calls = {"write": 0}
    import pathlib
    orig_write = pathlib.Path.write_text
    def bad_write(path, text, encoding='utf-8'):
        calls['write'] += 1
        raise OSError('nope')
    monkeypatch.setattr(Path, 'write_text', bad_write)
    # tests dir doesn't exist -> build_test_index triggers _write_index_meta
    _ = checks.build_test_index(tmp_path)
    assert calls['write'] >= 1
    # restore write_text for subsequent writes
    monkeypatch.setattr(Path, 'write_text', orig_write)
    # create invalid meta and ensure read_index_meta returns ""
    (tmp_path / '.mcp/test_index_meta.json').parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / '.mcp/test_index_meta.json').write_text('{invalid', encoding='utf-8')
    sig = checks._read_index_meta(tmp_path)
    assert sig == ""


def test_read_last_fail_invalid_json(tmp_path: Path) -> None:
    (tmp_path / '.mcp').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.mcp/last_failed_tests.json').write_text('{invalid', encoding='utf-8')
    r = checks.run_quick_tests([], cwd=tmp_path)
    assert r.get('skipped')
