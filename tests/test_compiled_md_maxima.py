from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_compiled_markdown_includes_maxima(tmp_path: Path) -> None:
    d = tmp_path / "doc.md"
    d.write_text("- 覆盖率 不超过 95%", encoding="utf-8")
    res = ri.ingest([str(d)], project_root=tmp_path)
    comp = res.get("compiled") or {}
    md_path = Path(comp.get("compiled_md") or "")
    assert md_path.exists()
    text = md_path.read_text(encoding="utf-8")
    assert "coverage.max_module" in text and "(monitor)" in text
