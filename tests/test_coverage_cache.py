from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.coverage_summary import summarize


def _write_cov(path: Path, a: float = 0.905, b: float = 0.88) -> None:
    path.write_text(
        "<coverage>\n  <packages><package><classes>\n"
        f'<class filename="pkg/a.py" line-rate="{a:.3f}"/>\n'
        f'<class filename="pkg/b.py" line-rate="{b:.3f}"/>\n'
        "</classes></package></packages>\n</coverage>\n",
        encoding="utf-8",
    )


def test_coverage_cache_file_created_and_updates(tmp_path: Path) -> None:
    covxml = tmp_path / "coverage.xml"
    _write_cov(covxml, a=0.905, b=0.880)
    # first run creates cache
    res1 = summarize(project_root=tmp_path)
    cache = tmp_path / ".mcp/coverage_cache.json"
    assert cache.exists()
    data = json.loads(cache.read_text(encoding="utf-8"))
    assert "files" in data and str(covxml.resolve()) in data["files"]
    rec1 = data["files"][str(covxml.resolve())]
    sig1 = rec1.get("sig")
    # modify coverage and ensure cache updates
    _write_cov(covxml, a=0.910, b=0.880)
    res2 = summarize(project_root=tmp_path)
    data2 = json.loads(cache.read_text(encoding="utf-8"))
    rec2 = data2["files"][str(covxml.resolve())]
    sig2 = rec2.get("sig")
    assert sig2 != sig1  # cache invalidated and refreshed
