from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_skip_code_fences_when_parsing_text(tmp_path: Path) -> None:
    d = tmp_path / "doc.md"
    d.write_text(
        "\n".join(
            [
                "- 覆盖率 90%",  # valid rule
                "",
                "```yaml",  # code fence start
                "- 覆盖率 100%",  # should be ignored
                "test:",
                "  warnings as errors: true",  # should be ignored
                "```",  # code fence end
            ]
        ),
        encoding="utf-8",
    )
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    # Should keep 90% and not be overridden to 100%
    assert abs(float(pol.get("coverage.min_module")) - 0.90) < 1e-6

