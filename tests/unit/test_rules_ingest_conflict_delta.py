from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_conflict_delta_per_key_override(tmp_path: Path) -> None:
    # Configure per-key delta to be stricter than default
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/assistant.yaml").write_text(
        """
rules:
  conflict_delta:
    __default__: 0.05
    coverage.min_module: 0.01
""".strip(),
        encoding="utf-8",
    )

    # Two inputs with 95% and 92% -> delta 0.03 > per-key 0.01 -> conflict expected
    f1 = tmp_path / "a.md"
    f2 = tmp_path / "b.md"
    f1.write_text("- 覆盖率 95%\n", encoding="utf-8")
    f2.write_text("- 覆盖率 92%\n", encoding="utf-8")

    res = ri.ingest([str(f1), str(f2)], project_root=tmp_path)
    compiled = res.get("compiled", {})
    assert compiled.get("ok") is True
    confs = compiled.get("conflicts", [])
    assert any(c.get("key") == "coverage.min_module" for c in confs)

    meta = compiled.get("meta", {})
    cd = meta.get("conflict_delta", {})
    # used per-key delta should be recorded
    assert cd.get("coverage.min_module") == 0.01
    # policy should keep stricter (max) value 0.95
    pol = compiled.get("policy", {})
    assert abs(float(pol.get("coverage.min_module", 0.0)) - 0.95) < 1e-9
