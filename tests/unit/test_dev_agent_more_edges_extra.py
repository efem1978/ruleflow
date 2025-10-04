from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mcp_rules_assistant.dev_agent import (
    DevAgent,
    _coverage_with_fallback,
    _scan_markdown_checklist,
)


def test_quick_status_fail_and_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    agent = DevAgent(project_root=tmp_path)

    # returncode != 0 -> "fail"
    def rc1(cmd, **kw):  # type: ignore[no-untyped-def]
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr("mcp_rules_assistant.dev_agent.run_cmd", rc1)
    st = agent._run_quick_status_check(["sh", "-c", "false"])  # nosec - test stub
    assert st == "fail"

    # raise -> "skipped"
    def boom(cmd, **kw):  # type: ignore[no-untyped-def]
        raise RuntimeError("tool missing")

    monkeypatch.setattr("mcp_rules_assistant.dev_agent.run_cmd", boom)
    st2 = agent._run_quick_status_check(["tool-not-exist"])  # type: ignore[list-item]
    assert st2 == "skipped"


def test_build_current_status_error_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    agent = DevAgent(project_root=tmp_path)

    # Force compute_status to raise to cover error branch
    def boom(*_a, **_k):  # noqa: ANN001
        raise RuntimeError("compute failed")

    monkeypatch.setattr(agent, "compute_status", boom, raising=True)
    status = agent._build_current_status(
        tests={"ok": False},
        bypass={"active": False},
        checks={"lint": "ok", "type": "ok", "tdd": "ok"},
        interval=60,
        cmd_error_count=0,
    )
    assert "error" in status


def test_scan_markdown_checklist_ignores_code_block(tmp_path: Path) -> None:
    md = tmp_path / "md.md"
    md.write_text(
        """
```
- [ ] inside code
- [x] inside code done
```
- [ ] outside pending
- [x] outside done
""",
        encoding="utf-8",
    )
    d, u, pend, done = _scan_markdown_checklist(md)
    assert d == 1 and u == 1
    assert "inside code" not in ",".join(pend + done)
    assert any("outside pending" in x for x in pend)
    assert any("outside done" in x for x in done)


def test_coverage_with_fallback_count_parse_error(tmp_path: Path) -> None:
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    # Previous status with non-integer count to exercise except path
    prev = {"coverage": {"weak": [], "groups": [], "near": [], "count": "NaN"}}
    (dash / "status.json").write_text(json.dumps(prev), encoding="utf-8")

    weak, groups, near, count = _coverage_with_fallback(
        tmp_path,
        {"weak": [], "count": 0},
        {"groups": []},
        {"near": []},
    )
    assert (
        isinstance(weak, list) and isinstance(groups, list) and isinstance(near, list)
    )
    assert count == 0  # parse error should fall back to 0
