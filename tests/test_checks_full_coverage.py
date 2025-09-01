from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.checks as checks


def test_run_checks_lint_type_and_skip_tests(monkeypatch, tmp_path: Path) -> None:
    # create a non-py file so lint skips
    f = tmp_path / 'a.txt'
    f.write_text('x', encoding='utf-8')
    called = {"lint": False, "type": False}

    def fake_run(cmd, cwd=None, env=None):
        # simulate both ruff and mypy ok
        if cmd and cmd[0] == 'ruff':
            called['lint'] = True
        if cmd and cmd[0] == 'mypy':
            called['type'] = True
        return {"ok": True, "code": 0, "stdout": "", "stderr": "", "cmd": cmd}

    monkeypatch.setattr(checks, '_run', fake_run)
    res = checks.run_checks([f], cwd=tmp_path, do_lint=True, do_type=True, do_quick_tests=True)
    assert res.get('ok') is True
    steps = res.get('steps') or []
    assert any('lint' in s for s in steps)
    assert any('type' in s for s in steps)
    assert any('tests' in s for s in steps)


def test_run_lint_and_type_paths(monkeypatch, tmp_path: Path) -> None:
    py = tmp_path / 'x.py'
    py.write_text('print(1)\n', encoding='utf-8')
    seen = []

    def fake_run(cmd, cwd=None, env=None):
        seen.append(cmd)
        return {"ok": True, "code": 0, "stdout": "", "stderr": "", "cmd": cmd}

    monkeypatch.setattr(checks, '_run', fake_run)
    r1 = checks.run_lint([py], cwd=tmp_path)
    r2 = checks.run_typecheck(cwd=tmp_path)
    assert r1.get('ok') is True and r2.get('ok') is True
    # ensure ruff check invoked with file
    assert any(cmd and cmd[0] == 'ruff' for cmd in seen)


def test_build_and_load_test_index_and_no_impacted(monkeypatch, tmp_path: Path) -> None:
    # no tests dir → build_index writes empty cache and load returns {}
    idx = checks.build_test_index(tmp_path)
    assert idx == {}
    idx2 = checks.load_test_index(tmp_path)
    assert idx2 == {}
    # run_quick_tests returns skipped when no impacted
    res = checks.run_quick_tests([], cwd=tmp_path)
    assert res.get('skipped') is True

