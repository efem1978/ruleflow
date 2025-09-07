from __future__ import annotations

import json
from pathlib import Path

import mcp_rules_assistant.rules_ingest as ri


def test_interpret_policy_core_between_english_and_chinese() -> None:
    out_en = ri._interpret_policy("between 80 and 90 percent core")
    assert "coverage.min_core" in out_en and "coverage.max_core" in out_en
    out_cn = ri._interpret_policy("核心 介于 80 和 90 之间")
    assert "coverage.min_core" in out_cn and "coverage.max_core" in out_cn


def test_english_words_to_int_empty() -> None:
    assert ri._english_words_to_int("") is None


def test_ingest_reads_cache_invalid_and_bad_items(tmp_path: Path) -> None:
    d = tmp_path / "docs"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "a.md"
    f.write_text("- 覆盖率 90%\n", encoding="utf-8")
    cache_path = tmp_path / ".mcp/rules_ingest_cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    # First write invalid JSON to hit except branch
    cache_path.write_text("{invalid", encoding="utf-8")
    out = ri.ingest([str(d)], project_root=tmp_path)
    assert out.get("files") >= 1
    # Now write a valid cache with bad item schema to hit inner except (reconstruction)
    st = f.stat()
    sig = f"{int(getattr(st,'st_mtime_ns', int(st.st_mtime*1e9)))}-{st.st_size}"
    cache = {
        "files": {
            str(f): {
                "sig": sig,
                "items": [
                    {
                        "key": "x",
                        "value": 1,
                        "text": "t",
                        "source": {"file": "x", "line": 1},
                    },
                    {"key": "bad"},
                ],
            }
        }
    }
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    out2 = ri.ingest([str(d)], project_root=tmp_path)
    assert out2.get("files") >= 1


def test_to_markdown_handles_nonfloat_maxima() -> None:
    compiled = {
        "policy": {},
        "conflicts": [],
        "meta": {"maxima": {"coverage.max_module": "bad"}},
    }
    md = ri._to_markdown(compiled)
    assert "Project Rules" in md
