from __future__ import annotations

import types
from pathlib import Path
import time

import mcp_rules_assistant.dev_agent as da


def test_run_tests_with_coverage_file_not_found(tmp_path: Path, monkeypatch) -> None:
    agent = da.DevAgent(tmp_path)

    def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise FileNotFoundError('no python')

    monkeypatch.setattr(da, 'run_cmd', boom)
    out = agent._run_tests_with_coverage()
    assert out.get('ok') is False and out.get('code') == 127


def test_git_changed_files_typeerror_and_parse(tmp_path: Path, monkeypatch) -> None:
    agent = da.DevAgent(tmp_path)

    class P:
        returncode = 0
        stdout = ' M foo.py\nA  bar.txt\n\n'
        stderr = ''

    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        if 'on_event' in kwargs:
            raise TypeError('unexpected on_event')
        return P()

    monkeypatch.setattr(da, 'run_cmd', fake_run)
    files = agent._git_changed_files()
    assert any(p.name in ('foo.py', 'bar.txt') for p in files)


def test_ensure_dashboard_dir_rebuild_handles_rmtree_error(tmp_path: Path, monkeypatch) -> None:
    agent = da.DevAgent(tmp_path)
    d = tmp_path / da.MCP_DIR_NAME / da.DASHBOARD_SUBDIR
    d.mkdir(parents=True, exist_ok=True)

    def bad_rmtree(p):  # type: ignore[no-untyped-def]
        raise OSError('boom')

    monkeypatch.setattr(da.shutil, 'rmtree', bad_rmtree)
    out = agent._ensure_dashboard_dir(rebuild=True)
    assert out.exists()


def test_compute_status_read_plan_error(tmp_path: Path, monkeypatch) -> None:
    def bad_read(_root: Path) -> str:
        raise RuntimeError('bad plan')

    monkeypatch.setattr(da, 'read_plan', bad_read)
    out = da.compute_status(tmp_path)
    assert isinstance(out.get('plan'), dict)


def test_update_wrappers_call_paths(tmp_path: Path, monkeypatch) -> None:
    agent = da.DevAgent(tmp_path)
    called = {'bypass': False, 'freeze': False}

    def fake_update_bypass(tests, run_config):  # type: ignore[no-untyped-def]
        called['bypass'] = True
        return tests, {'active': True}

    def fake_update_freeze(status, dash):  # type: ignore[no-untyped-def]
        called['freeze'] = True
        status['mutated'] = True

    monkeypatch.setattr(agent, '_update_bypass_status', fake_update_bypass)
    monkeypatch.setattr(agent, '_update_failure_and_freeze_status', fake_update_freeze)

    tests = {'ok': False}
    run_cfg = {'bypass_enabled': True}
    t2, b2 = da.update_bypass(agent, tests, run_cfg)
    assert called['bypass'] and isinstance(b2, dict)

    status = {'checks': {}}
    out = da.update_failure_and_freeze(agent, status, tmp_path)
    assert called['freeze'] and out.get('mutated') is True


def test_auto_commit_outer_exception(tmp_path: Path, monkeypatch) -> None:
    agent = da.DevAgent(tmp_path)
    # prepare plan
    p = tmp_path / '.mcp/plan.md'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('# 计划\n- 状态: in_progress\n- 当前步骤: demo\n', encoding='utf-8')

    def always_boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError('git failed')

    monkeypatch.setattr(da, 'run_cmd', always_boom)
    tests = {'ok': True}
    bypass = {'active': False}
    rc = {'auto_commit': True, 'commit_interval': 0}
    t = agent._handle_auto_commit(tests, bypass, rc, last_commit_ts=0.0)
    assert isinstance(t, float) and t == 0.0  # unchanged due to exception path


def test_auto_tag_outer_exception(tmp_path: Path, monkeypatch) -> None:
    agent = da.DevAgent(tmp_path)

    def always_boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError('git failed')

    monkeypatch.setattr(da, 'run_cmd', always_boom)
    tests = {'ok': True, 'mode': 'full'}
    status = {'coverage': {'weak': []}}
    rc = {'auto_tag': True}
    today = time.strftime('%Y%m%d', time.localtime())
    out = agent._handle_auto_tag(tests, status, rc, last_tag_date=today)
    assert out == today


def test_git_changed_files_exception_returns_empty(tmp_path: Path, monkeypatch) -> None:
    agent = da.DevAgent(tmp_path)

    def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError('oops')

    monkeypatch.setattr(da, 'run_cmd', boom)
    files = agent._git_changed_files()
    assert files == []
