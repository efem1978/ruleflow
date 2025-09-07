from pathlib import Path

from mcp_rules_assistant.rules_ingest import compile_rules


def test_compile_rules_no_raw_returns_false(tmp_path: Path) -> None:
    # When no raw rules ingested yet
    res = compile_rules(project_root=tmp_path)
    assert res.get("ok") is False
    assert "no raw rules" in str(res.get("message", ""))
