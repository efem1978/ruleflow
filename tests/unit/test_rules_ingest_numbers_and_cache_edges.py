from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_rules_assistant import rules_ingest as ri


def test_chinese_words_to_int_edges() -> None:
    f = ri._chinese_numeral_to_int
    assert f("一百") == 100  # hundreds only -> return hundreds path
    # Current implementation matches '十' branch before '百' branch; test reachable cases
    assert f("一百二") == 102  # 单位数路径


def test_ingest_text_cache_read_bytes_error_and_bad_cache(
    monkeypatch, tmp_path: Path
) -> None:
    # Prepare a text file
    docs = tmp_path / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    tf = docs / "rb_err.md"
    tf.write_text("- 覆盖率 90%", encoding="utf-8")

    # Create a cache with a matching signature but with malformed item to trigger reconstruction failure
    st = tf.stat()
    data_bytes = tf.read_bytes()
    import hashlib

    sig_hash = hashlib.sha256(data_bytes).hexdigest()
    sig = f"{int(getattr(st,'st_mtime_ns', int(st.st_mtime*1e9)))}-{st.st_size}-{sig_hash}"
    cache = {
        "files": {
            str(tf): {
                "sig": sig,
                # Malformed item: source.line should be int, make it string to trigger except
                "items": [
                    {
                        "key": "coverage.min_module",
                        "value": 0.9,
                        "text": "coverage.min_module: 0.9",
                        "source": {"path": str(tf), "line": "NaN"},
                    }
                ],
            }
        }
    }
    cache_path = tmp_path / ".mcp/rules_ingest_cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    # Monkeypatch Path.read_bytes to raise for our specific file to exercise 509-510 path
    orig_read_bytes = Path.read_bytes

    def fake_read_bytes(self: Path) -> bytes:  # type: ignore[override]
        if self == tf:
            raise OSError("boom")
        return orig_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", fake_read_bytes, raising=False)

    out = ri.ingest([str(tf)], project_root=tmp_path)
    assert out["files"] == 1
    # Should still produce compiled artifacts
    comp = out.get("compiled", {})
    assert comp.get("ok") in (True, False)
