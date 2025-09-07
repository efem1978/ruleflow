from __future__ import annotations

from pathlib import Path

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_apply_patch_refuses_symlink(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # create a real file and a symlink path that points to it
    real = tmp_path / "docs" / "a.txt"
    real.parent.mkdir(parents=True, exist_ok=True)
    real.write_text("x", encoding="utf-8")
    link = tmp_path / "docs" / "b.txt"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("symlink not supported on this platform")
    with pytest.raises(ValueError):
        srv._call_tool(
            "fs.apply_patch",
            {"files": [{"path": "docs/b.txt", "content": "new"}], "strict": True},
        )


def test_apply_patch_content_size_limit(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # tighten content limit via config patch on the fly
    srv.cfg.setdefault("execution", {})["max_content_bytes"] = 1024
    big = "x" * 2048
    with pytest.raises(ValueError):
        srv._call_tool(
            "fs.apply_patch",
            {"files": [{"path": "docs/c.txt", "content": big}], "strict": True},
        )
