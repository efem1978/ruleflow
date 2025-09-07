from __future__ import annotations

import subprocess
from pathlib import Path

from mcp_rules_assistant.process import run_cmd


def test_trim_len_excepts(monkeypatch, tmp_path: Path) -> None:
    class P:
        returncode = 0
        @property
        def stdout(self):  # type: ignore[no-untyped-def]
            raise RuntimeError('boom')
        @property
        def stderr(self):  # type: ignore[no-untyped-def]
            raise RuntimeError('boom')

    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return P()

    monkeypatch.setattr(subprocess, 'run', fake_run)
    p = run_cmd(["bash", "-lc", "true"], cwd=tmp_path, capture_stdout=True)
    assert getattr(p, 'returncode', 1) == 0

