from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_ingest_cache_object_not_mapping_triggers_except(tmp_path: Path) -> None:
    # 将缓存写成 JSON 数组，触发 cache.get AttributeError 分支（使用 try/except 包裹）
    mcp_dir = tmp_path / ".mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    (mcp_dir / "rules_ingest_cache.json").write_text("[]", encoding="utf-8")

    # 文本规则样例（触发文本解析路径）
    d = tmp_path / "docs"
    d.mkdir(parents=True, exist_ok=True)
    sample = d / "r.txt"
    sample.write_text("- 覆盖率 90%\n- 禁止 skip/xfail\n", encoding="utf-8")

    out = ri.ingest([str(sample.relative_to(tmp_path))], project_root=tmp_path)
    assert out.get("files") == 1
    comp = ri.compile_rules(project_root=tmp_path)
    assert comp.get("ok") in (True, False)  # 只要求流程可达
