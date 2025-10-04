from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.auto_status as AS


def test_collect_tasks_exception_branch(tmp_path: Path, monkeypatch) -> None:
    # 触发 collect_tasks 的异常分支（设置 _collect 抛异常）
    monkeypatch.setattr(
        AS,
        "_coverage_snapshot",
        lambda root=None: {
            "progress": 0.0,
            "weak": [],
            "groups": [],
            "near": [],
            "min_module": 0.9,
            "count": 0,
        },
    )
    monkeypatch.setattr(AS, "read_plan", lambda root=None: "- [ ] a\n")

    class Boom(Exception):
        pass

    def _boom(*a, **k):  # type: ignore[no-redef]
        raise Boom()

    monkeypatch.setattr(
        AS,
        "_plan_snapshot",
        lambda root=None: AS.PlanSnapshot("in_progress", "x", "y", 0, 1),
    )
    monkeypatch.setattr(
        AS,
        "_memory_snapshot",
        lambda root=None: {"exists": False, "summary": "", "turns": []},
    )
    # 注入会抛异常的 _collect
    monkeypatch.setattr(
        AS, "read_plan", lambda root=None: (_ for _ in ()).throw(Boom()),
    )
    out = AS.generate_status(project_root=tmp_path)
    assert out["tasks"]["pending"] == [] and out["tasks"]["done"] == []

    # 无法稳定制造 _coverage_snapshot 内部 len/float 异常（内部已做类型守护），此分支保持防御用途
