from mcp_rules_assistant import rules_ingest as ri


def test_interpret_policy_ignores_near_phrase() -> None:
    # Including 'within 3%' or '近阈值 3%' should not produce min_* thresholds
    out_en = ri._interpret_policy("coverage near within 3% for modules")
    out_cn = ri._interpret_policy("覆盖率 近阈值 3%")
    for out in (out_en, out_cn):
        assert "coverage.min_module" not in out
        assert "coverage.min_core" not in out
