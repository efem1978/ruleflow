from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_fs_apply_patch_soft_log_on_disallow(monkeypatch, tmp_path: Path) -> None:
    # 配置 disallow_patterns 并开启日志
    cfg_dir = tmp_path / ".mcp"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "assistant.yaml").write_text(
        """
execution:
  disallow_patterns: ["import pdb"]
        """.strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("MCP_FS_LOG", "1")

    from mcp_rules_assistant.config import load_config

    srv = JsonRpcServer()
    srv.project_root = tmp_path
    srv.cfg = load_config(tmp_path)

    # 应触发 disallow_patterns 命中（仅记录，不阻断）
    args = {
        "files": [{"path": "docs/demo.py", "content": "# test\nimport pdb\n"}],
        "runChecks": True,
        "strict": True,
        "dryRun": True,
    }
    out = srv._call_tool("fs.apply_patch", args)
    assert out.get("ok") is True
    assert "would_write" in out


## 说明：mcp_server 中基于 Path.resolve() 的实现会解析符号链接，
## 导致 is_symlink 检查不可达；对应分支由 fs_wrapper 覆盖充分，这里不重复测试。
