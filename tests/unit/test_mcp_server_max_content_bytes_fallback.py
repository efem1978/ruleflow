from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_fs_apply_patch_max_content_bytes_parse_fallback(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # 令 max_content_bytes 为不可转换的字符串，触发 except 分支并采用默认值
    srv.cfg.setdefault("execution", {})["max_content_bytes"] = "abc"  # type: ignore[index]
    out = srv._call_tool(
        "fs.apply_patch",
        {
            "files": [{"path": "ok.py", "content": "x"}],
            "runChecks": False,
            "dryRun": True,
        },
    )
    assert out.get("ok") is True
