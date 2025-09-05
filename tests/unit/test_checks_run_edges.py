from __future__ import annotations

from pathlib import Path
import types

from mcp_rules_assistant import checks
import sys


def test__run_importlib_failure_pipe_none(monkeypatch) -> None:
    # importlib.import_module fails -> _pipe=None, run called without stdout/stderr
    # Override importlib module seen inside _run
    def bad_import(name):  # noqa: ANN001
        raise RuntimeError('boom')
    ns = types.SimpleNamespace(import_module=bad_import)
    monkeypatch.setitem(sys.modules, 'importlib', ns)

    class P:
        def __init__(self):
            self.returncode = 0
            self.stdout = ''
            self.stderr = ''

    def fake_run(cmd, cwd=None, text=None, env=None):  # noqa: ANN001
        return P()

    monkeypatch.setattr(checks, 'subprocess', types.SimpleNamespace(run=fake_run))
    out = checks._run(['echo', 'ok'])
    assert out.get('ok') is True and out.get('code') == 0


def test__compute_tests_signature_stat_error(monkeypatch, tmp_path: Path) -> None:
    tests_dir = tmp_path / 'tests'
    tests_dir.mkdir(parents=True, exist_ok=True)
    target = tests_dir / 'test_a.py'
    target.write_text('def test_a(): pass\n', encoding='utf-8')
    import pathlib
    real_stat = pathlib.Path.stat

    def bad_stat(self):  # type: ignore[override]
        if self == target:
            raise OSError('nope')
        return real_stat(self)

    monkeypatch.setattr(pathlib.Path, 'stat', bad_stat)
    sig = checks._compute_tests_signature(tmp_path)
    assert isinstance(sig, str) and len(sig) > 0


def test_build_test_index_read_text_error(monkeypatch, tmp_path: Path) -> None:
    tdir = tmp_path / 'tests'; tdir.mkdir(parents=True, exist_ok=True)
    bad = tdir / 'test_x.py'
    bad.write_text('import pkg.mod\n', encoding='utf-8')
    import pathlib
    real_read = pathlib.Path.read_text

    def bad_read(self, *a, **k):  # noqa: ANN001
        if self == bad:
            raise OSError('nope')
        return real_read(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, 'read_text', bad_read)
    idx = checks.build_test_index(tmp_path)
    assert isinstance(idx, dict)


def test_run_quick_tests_config_yaml_error(monkeypatch, tmp_path: Path) -> None:
    # prepare mapping and tests so quick tests has something to run
    src = tmp_path / 'm/mod.py'; src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text('x=1\n', encoding='utf-8')
    t = tmp_path / 'tests/test_mod.py'; t.parent.mkdir(parents=True, exist_ok=True)
    t.write_text('def test_ok():\n assert True\n', encoding='utf-8')
    # break YAML load
    import pathlib
    real_read = pathlib.Path.read_text

    def bad_read(self, *a, **k):  # noqa: ANN001
        if str(self).endswith('/.mcp/assistant.yaml'):
            raise OSError('yml error')
        return real_read(self, *a, **k)

    # ensure yaml path exists so code hits read_text then raises
    (tmp_path / '.mcp').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.mcp/assistant.yaml').write_text('performance: {}\n', encoding='utf-8')
    monkeypatch.setattr(pathlib.Path, 'read_text', bad_read)
    # avoid invoking real pytest
    monkeypatch.setattr(checks, '_run', lambda *a, **k: {"ok": True, "code": 0, "stdout": '', "stderr": ''})
    out = checks.run_quick_tests([src], cwd=tmp_path)
    assert out.get('ok') is True


def test_run_quick_tests_events_missing_ts(monkeypatch, tmp_path: Path) -> None:
    # Prepare files
    src = tmp_path / 'm/mod.py'; src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text('x=1\n', encoding='utf-8')
    t = tmp_path / 'tests/test_mod.py'; t.parent.mkdir(parents=True, exist_ok=True)
    t.write_text('def test_ok():\n assert True\n', encoding='utf-8')
    # write last_failed with missing ts event to hit 'continue' branch
    (tmp_path / '.mcp').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.mcp/last_failed_tests.json').write_text(
        '{"events":[{"nodeid":"x::y","file":"tests/test_mod.py","ts":"0"}], "tests": [], "nodeids": []}',
        encoding='utf-8'
    )
    # avoid real pytest
    monkeypatch.setattr(checks, '_run', lambda *a, **k: {"ok": True, "code": 0, "stdout": '', "stderr": ''})
    out = checks.run_quick_tests([src], cwd=tmp_path)
    assert out.get('ok') is True
