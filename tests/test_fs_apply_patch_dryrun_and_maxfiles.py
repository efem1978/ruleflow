from __future__ import annotations

import os
from pathlib import Path

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer


def chdir(path: Path):
    class _Ctx:
        def __enter__(self):
            self._old = Path.cwd()
            os.chdir(path)
            return path

        def __exit__(self, exc_type, exc, tb):
            os.chdir(self._old)

    return _Ctx()


def test_apply_patch_dry_run_returns_would_write(tmp_path: Path) -> None:
    with chdir(tmp_path):
        srv = JsonRpcServer()
        res = srv._call_tool(
            "fs.apply_patch",
            {
                "files": [
                    {"path": "a.py", "content": "print('a')\n"},
                    {"path": "b.py", "content": "print('b')\n"},
                ],
                "runChecks": True,
                "strict": True,
                "dryRun": True,
            },
        )
        assert res.get("ok") is True
        assert int(res.get("written", -1)) == 0
        ww = res.get("would_write") or []
        assert any(str(tmp_path / "a.py") in w for w in ww)
        assert not (tmp_path / "a.py").exists()


def test_apply_patch_max_files_rejects(tmp_path: Path) -> None:
    with chdir(tmp_path):
        srv = JsonRpcServer()
        with pytest.raises(Exception) as e:
            srv._call_tool(
                "fs.apply_patch",
                {
                    "files": [
                        {"path": "a.py", "content": "print('a')\n"},
                        {"path": "b.py", "content": "print('b')\n"},
                        {"path": "c.py", "content": "print('c')\n"},
                    ],
                    "maxFiles": 2,
                },
            )
        assert "maxFiles" in str(e.value)
