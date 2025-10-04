from pathlib import Path

from mcp_rules_assistant.coverage_summary import (
    summarize,
    summarize_groups,
    summarize_near,
)


def test_summarize_handles_missing_coverage_xml(tmp_path: Path) -> None:
    # No coverage.xml in project
    res1 = summarize(project_root=tmp_path)
    res2 = summarize_groups(project_root=tmp_path)
    res3 = summarize_near(project_root=tmp_path)

    assert res1.get("ok") is False and "not found" in str(res1.get("message", ""))
    assert res2.get("ok") is False and "not found" in str(res2.get("message", ""))
    assert res3.get("ok") is False and "not found" in str(res3.get("message", ""))


def test_summarize_tolerates_corrupted_cache(tmp_path: Path) -> None:
    # Write a minimal coverage.xml
    cov = tmp_path / "coverage.xml"
    cov.write_text(
        """
        <coverage lines-valid=\"1\" lines-covered=\"1\">
          <packages>
            <classes>
              <class filename=\"pkg/mod.py\" line-rate=\"1.0\" lines-valid=\"1\" lines-covered=\"1\" />
            </classes>
          </packages>
        </coverage>
        """,
        encoding="utf-8",
    )
    # Write a corrupted cache to ensure code handles it
    cache = tmp_path / ".mcp/coverage_cache.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("{not-json}", encoding="utf-8")

    # Should parse xml fresh and not crash
    res = summarize(project_root=tmp_path)
    assert res.get("ok") is True
    assert int(res.get("count", 0)) >= 1
