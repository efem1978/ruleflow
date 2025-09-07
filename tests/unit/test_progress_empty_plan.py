from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.progress import update_plan_fields


def test_update_plan_fields_empty_file(tmp_path: Path) -> None:
    p = tmp_path / '.mcp/plan.md'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('', encoding='utf-8')
    # no updates provided: ensure it still writes a trailing newline branch
    update_plan_fields(tmp_path)
    assert p.read_text(encoding='utf-8').endswith('\n')

