from mcp_rules_assistant import rules_ingest as ri


def test_to_rules_md_includes_maxima_and_flags() -> None:
    compiled = {
        "policy": {
            "test.no_skip_xfail": True,
            "test.warnings_as_errors": True,
            "coverage.min_module": 0.95,
            "coverage.min_core": 0.98,
            "security.secrets_scan": True,
            "container.required": True,
            "ci.required": True,
            "vcs.conventional_commits": True,
            "vcs.branch_policy": True,
            "dev.tdd": True,
            "process.strict_order": True,
        },
        "meta": {
            "maxima": {
                "coverage.max_module": 0.99,
                "coverage.max_core": 1.00,
            }
        },
        "conflicts": [
            {"key": "coverage.min_module", "old": 0.9, "new": 0.95, "keep": 0.95},
        ],
    }
    md = ri._to_markdown(compiled)
    assert "项目规则" in md
    assert "coverage.min_module: 95%" in md
    assert "coverage.max_module: 99% (monitor)" in md
    assert "## 冲突 / Conflicts" in md


def test_to_suggestions_md_value_and_no_value() -> None:
    compiled = {
        "conflicts": [],
        "suggestions": [
            {
                "key": "test.no_skip_xfail",
                "action": "enforce",
                "note": "n/a",
                "severity": "must",
            },
            {
                "key": "coverage.min_module",
                "action": "enforce",
                "value": 0.95,
                "note": "n/a",
                "severity": "must",
            },
        ],
    }
    md = ri._to_suggestions_md(compiled)
    assert "## 建议" in md
    # one without value
    assert "[enforce] test.no_skip_xfail" in md
    # one with value
    assert "[enforce] coverage.min_module → 0.95" in md
