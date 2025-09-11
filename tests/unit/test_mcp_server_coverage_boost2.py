from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _srv(tmp_path: Path) -> JsonRpcServer:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # 确保从临时项目根读取配置
    srv.cfg = {
        "execution": {
            "disallow_patterns": [],
            "disallow_patterns_hard": False,
            "allowed_write_prefixes": [],
            "allowed_write_extensions": [],
        }
    }
    # 同步 FSGuard 的项目根与配置，避免落盘到仓库根
    srv.fs.project_root = tmp_path
    srv.fs.cfg = srv.cfg
    return srv


def test_fs_apply_patch_disallow_patterns_soft_allows(tmp_path: Path) -> None:
    srv = _srv(tmp_path)
    # 配置“软拦截”：命中片段仅记录，不拒绝
    srv.cfg.setdefault("execution", {})["disallow_patterns"] = ["FORBIDDEN"]
    srv.cfg["execution"]["disallow_patterns_hard"] = False
    # 命中受禁片段（软拦截），应允许写入
    srv._call_tool(
        "fs.apply_patch",
        {
            "files": [{"path": "foo.py", "content": "print('FORBIDDEN token')\n"}],
            "runChecks": True,
            "strict": True,
        },
    )
    assert (tmp_path / "foo.py").exists()


def test_fs_apply_patch_strict_rejects_skip_marker(tmp_path: Path) -> None:
    srv = _srv(tmp_path)
    # strict+runChecks 下，出现 skip/xfail 需拒绝
    with pytest.raises(ValueError):
        srv._call_tool(
            "fs.apply_patch",
            {
                "files": [
                    {
                        "path": "bar.py",
                        "content": "import pytest\npytest.mark.skip()\n",
                    }
                ],
                "runChecks": True,
                "strict": True,
            },
        )


def test_prompts_enabled_list_and_get(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    srv = _srv(tmp_path)
    # 通过环境变量开启 prompts
    monkeypatch.setenv("MCP_PROMPTS_ENABLE", "1")
    resp_list = srv.handle({"id": 1, "method": "prompts/list", "params": {}})
    assert resp_list["result"]["prompts"], "prompts should be listed when enabled"
    resp_get = srv.handle(
        {"id": 2, "method": "prompts/get", "params": {"name": "rules.summary"}}
    )
    assert resp_get["result"].get("ok") is True
    # 未知名称返回 not found
    resp_bad = srv.handle(
        {"id": 3, "method": "prompts/get", "params": {"name": "not.exists"}}
    )
    assert resp_bad["result"].get("ok") is False


def test_rules_maxima_resource_and_missing(tmp_path: Path) -> None:
    srv = _srv(tmp_path)
    pid = srv._project_id()
    # 先请求缺失时的错误路径
    err = srv.handle(
        {
            "id": 1,
            "method": "resources/read",
            "params": {"uri": f"rules://project/{pid}/maxima"},
        }
    )
    assert err["error"]["code"] in (-32602, -32001)

    # 写入最小编译结果，包含 maxima
    d = tmp_path / ".mcp"
    d.mkdir(parents=True, exist_ok=True)
    pjson = d / "rules_compiled.json"
    pjson.write_text(
        json.dumps(
            {"meta": {"maxima": {"coverage.max_core": 0.99}}}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    ok = srv.handle(
        {
            "id": 2,
            "method": "resources/read",
            "params": {"uri": f"rules://project/{pid}/maxima"},
        }
    )
    text = ok["result"]["text"]
    data = json.loads(text)
    assert data.get("maxima", {}).get("coverage.max_core") == 0.99


def test_fs_apply_patch_rejects_symlink_target(tmp_path: Path) -> None:
    srv = _srv(tmp_path)
    # 先创建符号链接作为目标文件
    target = tmp_path / "real.py"
    target.write_text("print('hi')\n", encoding="utf-8")
    link = tmp_path / "link.py"
    try:
        link.symlink_to(target)
    except Exception:
        pytest.skip("symlink not supported on this platform")
    # 由于内部对路径执行 resolve()，此处将实际落盘到真实文件（非链接）
    srv._call_tool(
        "fs.apply_patch",
        {
            "files": [{"path": "link.py", "content": "print('overwrite')\n"}],
            "runChecks": False,
            "strict": False,
        },
    )
    assert target.read_text(encoding="utf-8").strip() == "print('overwrite')"


def test_coverage_export_without_coverage_returns_error(tmp_path: Path) -> None:
    srv = _srv(tmp_path)
    out = srv._call_tool("coverage.export", {})
    assert out.get("ok") is False
    assert "coverage" in str(out.get("message", ""))


def test_license_verify_exception_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    srv = _srv(tmp_path)
    # 让 _verify_license 抛异常，覆盖异常返回分支
    from mcp_rules_assistant import mcp_server as srv_mod

    def _boom():
        raise RuntimeError("broken")

    monkeypatch.setattr(srv_mod, "_verify_license", _boom)
    out = srv._call_tool("license.verify", {})
    assert out.get("ok") is False
    assert "broken" in str(out.get("message", ""))
