from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_rules_onboard_complexity_heuristics_large(tmp_path: Path) -> None:
    # 构造一个临时项目，包含 >300 个 tests 文件，触发 large 分支
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    for i in range(0, 305):
        (tests_dir / f"test_{i}.py").write_text("pass\n", encoding="utf-8")

    srv = JsonRpcServer()
    srv.project_root = tmp_path

    # 不传 complexity，让启发式生效
    out = srv._call_tool("rules.onboard", {"apply": False})
    # 只校验输出结构存在，具体阈值由 choose_thresholds 决定
    assert out.get("ok") is True
    th = out.get("thresholds")
    # explain_thresholds 返回字符串摘要，允许实现返回字符串或结构化对象
    assert isinstance(th, (dict, str)) and ("min_module" in str(th))


def test_rules_onboard_invalid_enums_fallback(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # 传入非法 scenario/complexity 值，触发异常并走 fallback 分支
    out = srv._call_tool(
        "rules.onboard",
        {"scenario": "__bad__", "complexity": "__bad__", "apply": False},
    )
    assert out.get("ok") is True
    th = out.get("thresholds")
    assert isinstance(th, (dict, str)) and ("min_module" in str(th))
