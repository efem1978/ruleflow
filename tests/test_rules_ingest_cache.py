from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_rules_ingest_cache_created_and_used(tmp_path: Path) -> None:
    d = tmp_path / "doc.md"
    d.write_text("- 覆盖率 90%\n", encoding="utf-8")
    ri.ingest([str(d)], project_root=tmp_path)
    cache = tmp_path / ".mcp/rules_ingest_cache.json"
    assert cache.exists()
    data = json.loads(cache.read_text(encoding="utf-8"))
    assert "files" in data and str((tmp_path / "doc.md")) in data["files"]
    # Modify file to invalidate cache
    d.write_text("- 覆盖率 91%\n", encoding="utf-8")
    ri.ingest([str(d)], project_root=tmp_path)
    data2 = json.loads(cache.read_text(encoding="utf-8"))
    assert (
        data2["files"][str((tmp_path / "doc.md"))]["sig"]
        != data["files"][str((tmp_path / "doc.md"))]["sig"]
    )
