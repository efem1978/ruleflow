from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_plan_suggest_uses_summary_when_no_next(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # write plan without next
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/plan.md").write_text(
        "# 计划\n- 状态: in_progress\n- 当前步骤: C\n", encoding="utf-8",
    )
    # add memory summary with 下一步
    srv._call_tool(
        "memory.append_turn",
        {"role": "assistant", "content": "总结：已完成；下一步：完善文档"},
    )
    out = srv._call_tool("plan.suggest_next", {})
    s = out.get("suggestions", {})
    assert any("下一步" in x for x in s.get("next_steps", []))


def test_plan_suggest_falls_back_to_current(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/plan.md").write_text(
        "# 计划\n- 状态: in_progress\n- 当前步骤: C\n", encoding="utf-8",
    )
    # add summary without 下一步
    srv._call_tool("memory.append_turn", {"role": "assistant", "content": "总结：完成"})
    out = srv._call_tool("plan.suggest_next", {})
    s = out.get("suggestions", {})
    steps = s.get("next_steps", [])
    hp = s.get("handoff_plan", "")
    assert (isinstance(steps, list) and steps) or ("当前: C" in hp or "继续" in hp)


def test_config_get_update_invalid_yaml(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    # Create directory at file path to force read_text to fail
    cfg.mkdir(parents=True, exist_ok=True)
    # get should recover to {}
    got = srv._call_tool("config.get", {"section": None})
    assert got.get("ok") is True and isinstance(got.get("config"), dict)
    # for update, ensure file exists (normal path), still should succeed
    d = cfg
    if d.exists():
        # replace directory with file
        import shutil

        shutil.rmtree(d)
    d.write_text("x: 1", encoding="utf-8")
    up = srv._call_tool("config.update", {"data": {"hadolint": True}})
    assert up.get("ok") is True and up.get("ci", {}).get("hadolint") is True
