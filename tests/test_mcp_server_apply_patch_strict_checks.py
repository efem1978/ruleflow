from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_fs_apply_patch_strict_fails_on_checks(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # write code that fails mypy typecheck (int return annotated but returns str)
    content = 'def f() -> int:\n    return "x"\n'
    try:
        srv._call_tool(
            "fs.apply_patch",
            {
                "files": [{"path": "bad.py", "content": content}],
                "runChecks": True,
                "strict": True,
            },
        )
        assert False, "expected strict checks failure"
    except Exception as e:
        assert "检查未通过" in str(e) or "受控写入后的检查未通过" in str(e)
