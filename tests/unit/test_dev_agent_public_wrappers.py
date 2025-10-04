from __future__ import annotations

import types
from pathlib import Path

import mcp_rules_assistant.dev_agent as dev


def test_public_wrappers(tmp_path: Path, monkeypatch) -> None:
    a = dev.DevAgent(project_root=tmp_path)
    # update_bypass wrapper
    tests = {"ok": True}
    out_tests, bypass = dev.update_bypass(a, tests, {"bypass": False})
    assert isinstance(out_tests, dict) and isinstance(bypass, dict)

    # update_failure_and_freeze wrapper
    st = {"progress": {}, "coverage": {}}
    monkeypatch.setattr(
        a,
        "_update_failure_and_freeze_status",
        types.MethodType(lambda self, status, dash: None, a),
    )
    out = dev.update_failure_and_freeze(a, st, tmp_path)
    assert isinstance(out, dict)
