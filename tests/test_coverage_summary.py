from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.coverage_summary import summarize, summarize_groups


def _write_cov_xml(path: Path) -> None:
    text = (
        "<coverage>\n"
        "  <packages><package><classes>\n"
        "    <class filename=\"mcp_rules_assistant/foo.py\" line-rate=\"0.91\" lines-valid=\"100\" lines-covered=\"91\"/>\n"
        "    <class filename=\"other/bar.py\" line-rate=\"0.88\" lines-valid=\"100\" lines-covered=\"88\"/>\n"
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    path.write_text(text, encoding="utf-8")


def test_summarize_weak_items_and_thresholds(tmp_path: Path) -> None:
    cov = tmp_path / "coverage.xml"
    _write_cov_xml(cov)
    res = summarize(project_root=tmp_path, policy={"mcp_rules_assistant/": 0.95}, min_module=0.90)
    assert res.get("ok") is True
    weak = res.get("weak") or []
    # Both files should be under threshold
    files = [w.get("file") for w in weak]
    assert "other/bar.py" in files
    assert "mcp_rules_assistant/foo.py" in files
    # Prefix policy threshold applied for the assistant module
    for w in weak:
        if w.get("file") == "mcp_rules_assistant/foo.py":
            assert abs(float(w.get("threshold")) - 0.95) < 1e-6
        if w.get("file") == "other/bar.py":
            assert abs(float(w.get("threshold")) - 0.90) < 1e-6


def test_summarize_groups_aggregates_by_prefix(tmp_path: Path) -> None:
    cov = tmp_path / "coverage.xml"
    _write_cov_xml(cov)
    res = summarize_groups(project_root=tmp_path, policy={"mcp_rules_assistant/": 0.95}, min_module=0.90)
    assert res.get("ok") is True
    groups = {g.get("prefix"): g for g in res.get("groups") or []}
    assert "mcp_rules_assistant/" in groups
    assert "other" in groups
    g_assistant = groups["mcp_rules_assistant/"]
    assert abs(float(g_assistant.get("threshold")) - 0.95) < 1e-6
    assert int(g_assistant.get("files_count")) == 1
    g_other = groups["other"]
    assert abs(float(g_other.get("threshold")) - 0.90) < 1e-6
    assert int(g_other.get("files_count")) == 1

