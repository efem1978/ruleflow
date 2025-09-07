from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.coverage_summary import summarize


def _write_cov(path: Path) -> None:
    text = (
        "<coverage>\n"
        "  <packages><package><classes>\n"
        '    <class filename="mcp_rules_assistant/cli.py" line-rate="0.97" lines-valid="100" lines-covered="97"/>\n'
        '    <class filename="mcp_rules_assistant/license_utils.py" line-rate="0.92" lines-valid="100" lines-covered="92"/>\n'
        '    <class filename="other/foo.py" line-rate="0.94" lines-valid="100" lines-covered="94"/>\n'
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    path.write_text(text, encoding="utf-8")


def test_suffix_policy_overrides_prefix_and_min(tmp_path: Path) -> None:
    cov = tmp_path / "coverage.xml"
    _write_cov(cov)
    # Set min_module 0.96; file overrides:
    # - cli.py should use 0.98 (weak because 0.97 < 0.98)
    # - license_utils.py should use 0.90 (not weak because 0.92 >= 0.90)
    # - other/foo.py uses min_module 0.96 (weak because 0.94 < 0.96)
    policy = {
        "cli.py": 0.98,
        "license_utils.py": 0.90,
        "mcp_rules_assistant/": 0.96,
    }
    res = summarize(project_root=tmp_path, policy=policy, min_module=0.96)
    assert res.get("ok") is True
    weak_list = res.get("weak") or []
    assert isinstance(weak_list, list)
    weak = {
        str(w.get("file")): float(w.get("threshold", 0))
        for w in weak_list
        if isinstance(w, dict)
    }
    # cli and other/foo.py are weak; license_utils is not
    assert (
        "mcp_rules_assistant/cli.py" in weak
        and abs(weak["mcp_rules_assistant/cli.py"] - 0.98) < 1e-6
    )
    assert "other/foo.py" in weak and abs(weak["other/foo.py"] - 0.96) < 1e-6
    assert "mcp_rules_assistant/license_utils.py" not in weak
