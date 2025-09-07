from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_dev_tdd_and_strict_order_flags(tmp_path: Path) -> None:
    d = tmp_path / "dev.txt"
    d.write_text(
        "- 测试先行（TDD）；严格按顺序开发；no skipping steps", encoding="utf-8"
    )
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert pol.get("dev.tdd") is True
    assert pol.get("process.strict_order") is True
