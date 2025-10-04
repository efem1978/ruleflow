from __future__ import annotations

import json
from pathlib import Path


from mcp_rules_assistant import rules_ingest as ri


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_ingest_handles_maxima_non_numeric_and_merging(tmp_path: Path) -> None:
    # Prepare assistant.yaml with invalid conflict_delta values to hit exception paths
    conf = {
        "rules": {
            "conflict_delta": {
                "__default__": "bad",  # triggers except in global default parsing
                "coverage.min_module": "notnumber",  # triggers per-key float conversion except
            },
        },
    }
    write(tmp_path / ".mcp/assistant.yaml", json.dumps(conf))

    # YAML 1: duplicate non-numeric key to exercise stricter() fallback branch (returns 'a')
    write(tmp_path / "a.yaml", "custom:\n  note: alpha\n")
    # YAML 2: duplicate same key with different value (non-bool/non-numeric)
    write(tmp_path / "b.yaml", "custom:\n  note: beta\n")
    # YAML 3: maxima with non-numeric to trigger float() exception for maxima path
    write(tmp_path / "c.yaml", "coverage:\n  max_module: abc\n")

    out = ri.ingest([str(tmp_path)], project_root=tmp_path)
    assert out["compiled"]["ok"] is True
    comp_json = json.loads((tmp_path / ri.COMPILED_JSON).read_text(encoding="utf-8"))

    # Ensure suggestions and policy produced; non-numeric maxima ignored gracefully
    assert isinstance(comp_json.get("policy"), dict)
    # custom.note merged (keeps first occurrence due to stricter returning 'a')
    assert comp_json["policy"].get("custom.note") == "alpha"
    # maxima non-numeric should be skipped; ensure either missing or not coercible
    maxima = (comp_json.get("meta", {}) or {}).get("maxima", {})
    assert "coverage.max_module" not in maxima or isinstance(
        maxima.get("coverage.max_module"), (int, float),
    )


def test_chinese_numeral_edge_cases() -> None:
    # Exercise branches inside _chinese_numeral_to_int
    f = ri._chinese_numeral_to_int  # type: ignore[attr-defined]
    assert f("一百") == 100
    # 'endswith 十' and 'startswith 十' branches via common forms
    # rest endswith 十 and len==2
    assert f("二百三十") is not None
    # rest startswith 十 with optional unit
    assert f("三百十五") is not None
    # single digit
    assert f("九") == 9
    # unsupported pattern returns None
    assert f("九五") is None
