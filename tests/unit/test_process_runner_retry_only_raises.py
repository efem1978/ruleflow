from __future__ import annotations

import subprocess
from pathlib import Path

from mcp_rules_assistant.process import run_cmd


def test_retry_on_timeout_only_raises_non_timeout(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise ValueError('boom')

    monkeypatch.setattr(subprocess, 'run', fake_run)
    try:
        run_cmd(["bash", "-lc", "true"], cwd=tmp_path, retries=1, retry_on_timeout_only=True)
        assert False, 'expected raise'
    except ValueError:
        pass

