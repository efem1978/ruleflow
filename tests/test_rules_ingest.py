from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_ingest_compiles_rules_and_detects_conflicts(tmp_path: Path) -> None:
    # Prepare sample docs
    d1 = tmp_path / "doc1.md"
    d1.write_text(
        "\n".join(
            [
                "- 覆盖率 90%",  # min_module = 0.9
                "- 核心 95%",     # min_core = 0.95
                "- 禁止 skip/xfail",
                "- 变异测试 必须",
                "- 密钥 扫描",
                "- Dockerfile 存在",  # container.required
                "- 镜像基线",        # container.policy.baseline
            ]
        ),
        encoding="utf-8",
    )
    d2 = tmp_path / "doc2.md"
    d2.write_text("- 覆盖率 96%", encoding="utf-8")  # force stricter + conflict with 90%

    res = ri.ingest([str(d1), str(d2)], project_root=tmp_path)
    assert res.get("files") == 2
    compiled = res.get("compiled") or {}
    policy = compiled.get("policy") or {}
    # Stricter value kept
    assert abs(float(policy.get("coverage.min_module")) - 0.96) < 1e-6
    assert abs(float(policy.get("coverage.min_core")) - 0.95) < 1e-6
    assert policy.get("test.no_skip_xfail") is True
    assert policy.get("test.mutation_required") is True
    assert policy.get("security.secrets_scan") is True
    assert policy.get("container.required") is True
    assert policy.get("container.policy.baseline") is True
    # Conflict recorded
    conflicts = compiled.get("conflicts") or []
    assert any(c.get("key") == "coverage.min_module" for c in conflicts)
    # Suggestions include enforcement for coverage
    suggests = compiled.get("suggestions") or []
    assert any(s.get("key") == "coverage.min_module" for s in suggests)


def test_ingest_supports_yaml_and_json_inputs(tmp_path: Path) -> None:
    y = tmp_path / "rules.yaml"
    y.write_text(
        "\n".join([
            "coverage:",
            "  min_module: 0.91",
            "  min_core: 0.96",
            "security:",
            "  secrets_scan: true",
        ]),
        encoding="utf-8",
    )
    j = tmp_path / "rules.json"
    j.write_text('{"test": {"no_skip_xfail": true}}', encoding="utf-8")
    res = ri.ingest([str(y), str(j)], project_root=tmp_path)
    policy = (res.get("compiled") or {}).get("policy") or {}
    assert abs(float(policy.get("coverage.min_module")) - 0.91) < 1e-6
    assert abs(float(policy.get("coverage.min_core")) - 0.96) < 1e-6
    assert policy.get("security.secrets_scan") is True
    assert policy.get("test.no_skip_xfail") is True


def test_conflict_threshold_is_strictly_gt_5_percent(tmp_path: Path) -> None:
    # 90% vs 94% => diff 0.04 -> not a conflict (<=5%) but keep stricter
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("- 覆盖率 90%", encoding="utf-8")
    b.write_text("- 覆盖率 94%", encoding="utf-8")
    res = ri.ingest([str(a), str(b)], project_root=tmp_path)
    compiled = res.get("compiled") or {}
    policy = compiled.get("policy") or {}
    conflicts = compiled.get("conflicts") or []
    assert abs(float(policy.get("coverage.min_module")) - 0.94) < 1e-6
    assert not any(c.get("key") == "coverage.min_module" for c in conflicts)
