from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def _sig_for(p: Path) -> str:
    st = p.stat()
    try:
        data = p.read_bytes()
    except Exception:  # pragma: no cover
        data = b""
    h = hashlib.sha256(data).hexdigest()
    return f"{int(getattr(st,'st_mtime_ns', int(st.st_mtime*1e9)))}-{st.st_size}-{h}"


def test_ingest_text_cache_miss_and_exceptions(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path
    # create three markdown files
    a = root / "a.md"
    a.write_text("- coverage 90%\n", encoding="utf-8")
    b = root / "b.md"
    b.write_text("- coverage 95%\n", encoding="utf-8")
    c = root / "c.md"
    c.write_text("- coverage 96%\n", encoding="utf-8")
    # create a JSON file to hit YAML/JSON branch
    d = root / "d.json"
    d.write_text('{"x": 1}', encoding="utf-8")

    # prepare cache with a record for a.md that has correct sig but malformed items
    bad_item = {"value": 1, "text": "t", "source": {"file": str(a), "line": 1}}
    cache = {"files": {str(a): {"sig": _sig_for(a), "items": [bad_item]}}}
    (root / ".mcp").mkdir(parents=True, exist_ok=True)
    (root / ".mcp/rules_ingest_cache.json").write_text(
        json.dumps(cache), encoding="utf-8"
    )

    # monkeypatch Path.read_bytes to raise for b.md during sig compute (lines 494-495)
    import pathlib

    real_rb = pathlib.Path.read_bytes

    def rb(self: Path):  # type: ignore[override]
        if self == b:
            raise OSError("nope-b")
        return real_rb(self)

    monkeypatch.setattr(pathlib.Path, "read_bytes", rb)

    # run ingest on all files; ensure it completes and compiles
    out = ri.ingest([str(a), str(b), str(c), str(d)], project_root=root)
    assert out.get("files") == 4
    comp = out.get("compiled") or {}
    assert comp.get("ok", True) is not False

    # Now monkeypatch read_bytes to raise for c.md during write-cache phase (lines 529-531)
    def rb2(self: Path):  # type: ignore[override]
        if self == c:
            raise OSError("nope-c")
        return real_rb(self)

    monkeypatch.setattr(pathlib.Path, "read_bytes", rb2)
    out2 = ri.ingest([str(c)], project_root=root)
    assert out2.get("files") == 1 and (out2.get("compiled") or {}).get("ok", True)
