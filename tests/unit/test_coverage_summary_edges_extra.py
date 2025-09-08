from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.coverage_summary as cs


def test_threshold_for_file_policy_parse_error_defaults() -> None:
    # policy contains non-numeric threshold → parsing raises, should fallback to default
    default = 0.91
    th = cs._threshold_for_file("cli.py", policy={"cli.py": "not-a-number"}, default=default)  # type: ignore[arg-type]
    assert abs(th - default) < 1e-9


def test_read_invalid_coverage_xml_graceful(tmp_path: Path) -> None:
    # invalid XML should be treated as empty classes list → summarize returns ok with zero items
    (tmp_path / "coverage.xml").write_text("<not-coverage>", encoding="utf-8")
    out = cs.summarize(
        project_root=tmp_path, coverage_xml="coverage.xml", policy=None, min_module=0.9
    )
    assert out.get("ok") is True
    assert out.get("count") == 0
    assert out.get("weak") == []
