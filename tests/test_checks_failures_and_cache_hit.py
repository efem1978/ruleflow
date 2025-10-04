from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import checks


def test_run_quick_tests_records_failures(tmp_path: Path) -> None:
    # Create a failing test and ensure run_quick_tests captures it
    tdir = tmp_path / "tests"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "test_bad.py").write_text(
        "def test_bad():\n    assert 1==2\n", encoding="utf-8",
    )
    res = checks.run_quick_tests([tdir / "test_bad.py"], cwd=tmp_path)
    assert res.get("ok") is False or res.get("code", 0) != 0
    # last_failed_tests.json should exist with node info
    jf = tmp_path / ".mcp/last_failed_tests.json"
    assert jf.exists()
    text = jf.read_text(encoding="utf-8")
    assert "tests/test_bad.py" in text


def test_coverage_cache_hit_flow(tmp_path: Path) -> None:
    # Write coverage.xml and call summarize twice to exercise cache hit
    cov = tmp_path / "coverage.xml"
    cov.write_text(
        "<coverage>\n  <packages><package><classes>\n"
        '<class filename="a.py" line-rate="0.905"/>\n'
        "</classes></package></packages>\n</coverage>\n",
        encoding="utf-8",
    )
    from mcp_rules_assistant.coverage_summary import summarize

    r1 = summarize(project_root=tmp_path)
    assert r1.get("ok") is True
    # second call should read from cache path
    r2 = summarize(project_root=tmp_path)
    assert r2.get("ok") is True
