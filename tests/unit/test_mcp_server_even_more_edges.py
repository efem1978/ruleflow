from pathlib import Path

import yaml

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_plan_set_type_error(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    try:
        srv._call_tool("plan.set", {"status": 1})
        assert False, "expected ValueError for non-string status"
    except ValueError as e:
        assert "must be string" in str(e)


def test_env_prepare_packages_type_error(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    try:
        srv._call_tool("env.prepare", {"packages": [1, 2, 3]})
        assert False, "expected ValueError for bad packages"
    except ValueError as e:
        assert "packages must be a list of strings" in str(e)


def test_plan_suggest_next_from_summary(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp" / "plan.md").write_text("# 计划\n", encoding="utf-8")

    class Dummy:
        def snapshot(self):
            return {"summary": "请执行 下一步：完善文档 与测试，尽快交付"}

    srv.mm = Dummy()  # type: ignore[assignment]
    out = srv._call_tool("plan.suggest_next", {})
    assert out.get("ok") is True
    j = out.get("suggestions", {})
    assert any("下一步" in x for x in (j.get("next_steps") or []))


def test_plan_suggest_next_from_nxt_field(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp" / "plan.md").write_text("- 下一步: 做好单测\n", encoding="utf-8")
    out = srv._call_tool("plan.suggest_next", {})
    s = out.get("suggestions", {})
    assert any("做好单测" in x for x in (s.get("next_steps") or []))


def test_rules_ingest_paths_nonempty_strings(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    try:
        srv._call_tool("rules.ingest", {"paths": [""]})
        assert False, "expected ValueError for empty path"
    except ValueError as e:
        assert "paths must contain" in str(e)


def test_rules_onboard_detect_exception_fallback(tmp_path: Path, monkeypatch) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path

    def boom():  # noqa: ANN001
        raise RuntimeError("detect failed")

    monkeypatch.setattr(srv, "_tool_project_detect", boom, raising=True)
    out = srv._call_tool("rules.onboard", {"apply": False})
    assert out.get("ok") is True
    assert "thresholds" in out


def test_rules_onboard_apply_write_error(tmp_path: Path, monkeypatch) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp" / "assistant.yaml").write_text("{}\n", encoding="utf-8")

    def dump_boom(*_a, **_k):  # noqa: ANN001
        raise RuntimeError("yaml dump failed")

    monkeypatch.setattr(yaml, "safe_dump", dump_boom, raising=True)
    out = srv._call_tool("rules.onboard", {"apply": True})
    assert out.get("ok") is True
    assert out.get("applied") is False


def test_fs_apply_patch_max_content_bytes(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    srv.cfg = {"execution": {"max_content_bytes": 1}}
    try:
        srv._call_tool(
            "fs.apply_patch",
            {
                "files": [{"path": "docs/a.py", "content": "abcd"}],
                "runChecks": False,
                "strict": False,
                "dryRun": True,
            },
        )
        assert False, "expected size limit error"
    except ValueError as e:
        assert "超出大小限制" in str(e)


def test_config_get_bad_yaml(tmp_path: Path) -> None:
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp" / "assistant.yaml").write_text("\t\t: : : bad", encoding="utf-8")
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out = srv._call_tool("config.get", {})
    assert out.get("ok") is True and isinstance(out.get("config"), dict)
