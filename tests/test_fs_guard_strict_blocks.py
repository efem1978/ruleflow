from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.fs_wrapper import FSGuard


def test_fs_guard_strict_blocks_on_failed_checks(tmp_path: Path) -> None:
    # 启用 post checks + strict，并用打补丁的 run_checks 返回失败，以触发阻断
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        "execution:\n  fs_guard_post_checks: true\n  fs_guard_strict: true\n",
        encoding="utf-8",
    )

    import mcp_rules_assistant.checks as checks

    orig = checks.run_checks
    try:

        def fail(*a, **k):  # type: ignore[no-redef]
            return {"ok": False}

        checks.run_checks = fail  # type: ignore[assignment]
        g = FSGuard(project_root=tmp_path)
        # 容错：直接覆盖内存中的配置，确保严格模式开启
        g.cfg.setdefault("execution", {})
        g.cfg["execution"]["fs_guard_post_checks"] = True
        g.cfg["execution"]["fs_guard_strict"] = True
        try:
            g.write_text(Path("strict.py"), "print('x')\n")
            assert False, "strict mode expected to raise"
        except Exception as e:
            assert "FSGuard post checks failed" in str(e)
    finally:
        checks.run_checks = orig  # type: ignore[assignment]
