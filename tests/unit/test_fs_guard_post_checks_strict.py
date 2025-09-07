from __future__ import annotations

from pathlib import Path

import pytest

from mcp_rules_assistant.fs_wrapper import FSGuard


def test_post_checks_fail_in_strict_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    guard = FSGuard(tmp_path)
    exec_cfg = guard.cfg.setdefault("execution", {})
    exec_cfg["fs_guard_post_checks"] = True
    exec_cfg["fs_guard_strict"] = True

    def fake_run_checks(files, cwd, do_lint, do_type, do_quick_tests):  # type: ignore[no-untyped-def]
        return {"ok": False}

    monkeypatch.setattr("mcp_rules_assistant.checks.run_checks", fake_run_checks)
    with pytest.raises(Exception):
        guard.write_text(Path("src/x.py"), "print(1)")
