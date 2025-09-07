from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.fs_wrapper import FSGuard


def test_fs_guard_post_checks_handles_errors(tmp_path: Path) -> None:
    # 触发 try/except 分支：将 run_checks 打补丁抛异常
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("execution:\n  fs_guard_post_checks: true\n", encoding="utf-8")

    # 打补丁：让 run_checks 抛出异常
    import mcp_rules_assistant.checks as checks

    orig = checks.run_checks
    try:

        def boom(*a, **k):  # type: ignore[no-redef]
            raise RuntimeError("boom")

        checks.run_checks = boom  # type: ignore[assignment]
        guard = FSGuard(project_root=tmp_path)
        guard.write_text(Path("err.py"), "print('x')\n")
        # 不应抛异常
        assert (tmp_path / "err.py").exists()
    finally:
        checks.run_checks = orig  # type: ignore[assignment]


def test_fs_guard_post_checks_runs_without_error(tmp_path: Path) -> None:
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    # 启用 FSGuard 写入后检查（lint/type/受影响测试）；
    # checks 子系统在工具缺失时会自动降级为 skipped，不会抛错
    cfg.write_text("execution:\n  fs_guard_post_checks: true\n", encoding="utf-8")

    guard = FSGuard(project_root=tmp_path)
    rel = Path("sample.py")
    guard.write_text(rel, "print(123)\n")

    f = tmp_path / rel
    assert f.exists()
    assert "print(123)" in f.read_text(encoding="utf-8")
