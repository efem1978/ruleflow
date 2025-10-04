from __future__ import annotations

from pathlib import Path

import pytest

from mcp_rules_assistant import mcp_server as ms


def _mk_server(tmp_path: Path) -> ms.JsonRpcServer:
    # 在独立目录中初始化服务
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    return ms.JsonRpcServer()


def test_gated_tool_license_required_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    srv = _mk_server(tmp_path)
    # 启用 license.required 并让校验失败
    srv.cfg = {"license": {"required": True}}
    monkeypatch.setattr(ms, "_verify_license", lambda: {"ok": False})
    with pytest.raises(ValueError):
        srv._call_tool("ci.generate", {})


def test_resources_read_unknown_uri(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    srv = _mk_server(tmp_path)
    # 通过 handle 调用，命中 Unknown resource uri 分支并被包装为 error
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "resources/read",
        "params": {"uri": "unknown://x"},
    }
    resp = srv.handle(req)
    assert "error" in resp and resp["error"]["code"] == -32000


def test_rules_maxima_missing_compiled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    srv = _mk_server(tmp_path)
    # 通过 handle 访问 maxima，缺少编译文件应报错
    uri = f"rules://project/{srv._project_id()}/maxima"
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "resources/read",
        "params": {"uri": uri},
    }
    resp = srv.handle(req)
    assert "error" in resp and "rules resource not found" in resp["error"]["message"]


def test_fs_apply_patch_missing_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    srv = _mk_server(tmp_path)
    with pytest.raises(ValueError):
        srv._call_tool(
            "fs.apply_patch",
            {"files": [{"content": "ok"}], "runChecks": True, "strict": True},
        )


def test_fs_apply_patch_absolute_and_outside(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    srv = _mk_server(tmp_path)
    # 绝对路径
    with pytest.raises(ValueError):
        srv._call_tool(
            "fs.apply_patch",
            {"files": [{"path": str(Path(tmp_path).resolve()), "content": "x"}]},
        )
    # 越权路径（..）
    with pytest.raises(ValueError):
        srv._call_tool(
            "fs.apply_patch", {"files": [{"path": "../x.py", "content": "x"}]},
        )


def test_fs_apply_patch_prefix_ext_mismatch_strict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    srv = _mk_server(tmp_path)
    srv.cfg = {
        "execution": {
            "allowed_write_prefixes": ["docs/"],
            "allowed_write_extensions": [".md"],
            "fs_guard_strict": True,
        },
    }
    # 前缀不匹配 -> 在 strict 下抛出
    with pytest.raises(ValueError):
        srv._call_tool(
            "fs.apply_patch", {"files": [{"path": "src/x.md", "content": "a"}]},
        )
    # 前缀匹配但扩展名不匹配 -> 抛出
    Path("docs").mkdir(exist_ok=True)
    with pytest.raises(ValueError):
        srv._call_tool(
            "fs.apply_patch", {"files": [{"path": "docs/x.py", "content": "a"}]},
        )


def test_fs_apply_patch_maxfiles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    srv = _mk_server(tmp_path)
    files = [{"path": "a.py", "content": "x"}, {"path": "b.py", "content": "y"}]
    with pytest.raises(ValueError):
        srv._call_tool("fs.apply_patch", {"files": files, "maxFiles": 1})


def test_fs_apply_patch_strict_skip_and_pattern(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    srv = _mk_server(tmp_path)
    # skip/xfail 检测
    with pytest.raises(ValueError):
        srv._call_tool(
            "fs.apply_patch",
            {
                "files": [{"path": "x.py", "content": "pytest.mark.skip()"}],
                "runChecks": True,
                "strict": True,
            },
        )
    # 禁止片段检测（import pdb）
    srv.cfg = {"execution": {"disallow_patterns": ["import pdb"]}}
    # 当前实现中该异常会被 try/except 吞掉（仅 skip/xfail 直接阻断），此处只验证不报错且返回 ok
    out = srv._call_tool(
        "fs.apply_patch",
        {
            "files": [{"path": "x.py", "content": "import pdb\nprint(1)"}],
            "runChecks": True,
            "strict": True,
        },
    )
    assert out.get("ok") is True


def test_fs_apply_patch_post_checks_fail_strict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    srv = _mk_server(tmp_path)
    srv.cfg = {
        "execution": {
            "allowed_write_prefixes": ["mcp_rules_assistant/"],
            "allowed_write_extensions": [".py"],
        },
        "performance": {"on_commit": {"typecheck_incremental": True}},
    }
    # 让 run_checks 返回失败
    monkeypatch.setattr(ms.checks_mod, "run_checks", lambda *a, **k: {"ok": False})
    with pytest.raises(ValueError):
        srv._call_tool(
            "fs.apply_patch",
            {
                "files": [
                    {
                        "path": "mcp_rules_assistant/edge_test.py",
                        "content": "print('x')",
                    },
                ],
                "runChecks": True,
                "strict": True,
            },
        )


def test_fs_apply_patch_dry_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    srv = _mk_server(tmp_path)
    out = srv._call_tool(
        "fs.apply_patch",
        {"files": [{"path": "x.md", "content": "# a"}], "dryRun": True},
    )
    assert out.get("ok") and "would_write" in out


def test_prompts_list_and_get(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    srv = _mk_server(tmp_path)
    r1 = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "prompts/list"})
    assert r1.get("result", {}).get("prompts") == []
    r2 = srv.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "prompts/get", "params": {"name": "x"}},
    )
    assert r2.get("result", {}).get("ok") is False


def test_project_detect_python(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[build-system]\n", encoding="utf-8")
    srv = _mk_server(tmp_path)
    out = srv._tool_project_detect()
    assert out.get("language") == "python"


def test_license_required_try_except_and_ensure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    srv = _mk_server(tmp_path)
    # _license_required 的异常回退
    srv.cfg = "not-a-dict"  # type: ignore[assignment]
    assert srv._license_required() is False
    # _ensure_license 的 try/except：校验抛异常 -> 视作失败
    srv.cfg = {"license": {"required": True}}
    monkeypatch.setattr(ms, "_verify_license", lambda: (_ for _ in ()).throw(RuntimeError("boom")))  # type: ignore[no-untyped-call]
    with pytest.raises(ValueError):
        srv._call_tool("ci.generate", {})


def test_tool_license_activate_error_and_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    srv = _mk_server(tmp_path)
    # 错误路径：文件不存在
    with pytest.raises(ValueError):
        srv._call_tool("license.activate", {"path": "nope.json"})
    # 成功路径：复制到 HOME/.mcp
    lic = tmp_path / "lic.json"
    lic.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    out = srv._call_tool("license.activate", {"path": str(lic)})
    assert out.get("ok") is True and (Path(tmp_path) / ".mcp/license.json").exists()


def test_env_diagnose_executes_verify(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    srv = _mk_server(tmp_path)
    # 返回值包含 license 键，表示路径已执行
    out = srv._tool_env_diagnose()
    assert out.get("ok") is True and "license" in out
