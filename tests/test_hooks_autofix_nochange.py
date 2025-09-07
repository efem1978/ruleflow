from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import hooks


def test_autofix_returns_unchanged_when_same(tmp_path: Path) -> None:
    # First generate desired CI, then call autofix again to get changed=False
    p = hooks.generate_github_ci(tmp_path)
    assert p.exists()
    res = hooks.autofix_github_ci(tmp_path)
    assert res.get("changed") is False
    assert Path(res.get("path") or "").exists()
