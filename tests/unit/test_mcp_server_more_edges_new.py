from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_project_link_requires_args(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    try:
        srv._call_tool("project.link", {"project": "", "task": ""})
        assert False, "expected error"
    except Exception as e:
        assert "required" in str(e)


def test_memory_append_turn_meta_coerced(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool(
        "memory.append_turn", {"role": "user", "content": "c", "meta": "x"},
    )
    assert out.get("ok") is True


def test_config_update_read_yaml_exception(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("x: 1", encoding="utf-8")
    # remove read perms to trigger read error inside yaml.safe_load try
    import os

    os.chmod(cfg, 0)
    out = srv._call_tool("config.update", {"data": {"hadolint": True}})
    # restore perms for cleanup
    os.chmod(cfg, 0o644)
    assert out.get("ok") is True
