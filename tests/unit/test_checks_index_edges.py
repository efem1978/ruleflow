from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant import checks


def test_build_index_when_tests_missing_writes_meta(tmp_path: Path) -> None:
    # No tests directory -> returns empty and writes meta signature
    idx = checks.build_test_index(tmp_path)
    assert idx == {}
    meta = tmp_path / ".mcp/test_index_meta.json"
    assert meta.exists()


def test_load_index_invalid_json_and_signature_change(tmp_path: Path) -> None:
    # Prepare a tests dir with simple import lines
    tdir = tmp_path / "tests"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "test_parse_a.py").write_text("from acme.mod import a\n", encoding="utf-8")
    # Write an invalid index and mismatched meta to trigger rebuild
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/test_index.json").write_text("{invalid", encoding="utf-8")
    (tmp_path / ".mcp/test_index_meta.json").write_text(
        json.dumps({"sig": "old"}), encoding="utf-8"
    )
    out = checks.load_test_index(tmp_path)
    # Should rebuild and include the new mapping for acme.mod
    assert "acme.mod" in out or "acme" in out


def test_read_last_fail_invalid_returns_defaults(tmp_path: Path) -> None:
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/last_failed_tests.json").write_text("{invalid", encoding="utf-8")
    r = checks._read_last_fail(tmp_path)
    assert r.get("tests") == set() and r.get("nodeids") == set()
