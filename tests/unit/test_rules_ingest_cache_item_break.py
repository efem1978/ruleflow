from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def _sig_for(path: Path) -> str:
    st = path.stat()
    try:
        data_bytes = path.read_bytes()
    except Exception:
        data_bytes = b""
    sig_hash = hashlib.sha256(data_bytes).hexdigest()
    return f"{int(getattr(st,'st_mtime_ns', int(st.st_mtime*1e9)))}-{st.st_size}-{sig_hash}"


def test_cache_items_break_and_fallback_parse(tmp_path: Path) -> None:
    # Prepare a text file
    p = tmp_path / "r.txt"
    p.write_text("- 覆盖率 不低于 90%", encoding="utf-8")

    # Prepare a cache entry with invalid item to trigger except -> use_cache=False
    cache_dir = tmp_path / ".mcp"
    cache_dir.mkdir(parents=True, exist_ok=True)
    bad_items = [
        {
            "key": "coverage.min_module",
            "value": 0.9,
            "text": "min module",
            # invalid shape (missing 'line') to trigger TypeError on Source(**...)
            "source": {"file": str(p)},
        }
    ]
    cache = {"files": {str(p): {"sig": _sig_for(p), "items": bad_items}}}
    (cache_dir / "rules_ingest_cache.json").write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    out = ri.ingest([str(p)], project_root=tmp_path)
    assert out.get("files") == 1
    comp = out.get("compiled") or {}
    pol = comp.get("policy") or {}
    assert "coverage.min_module" in pol
