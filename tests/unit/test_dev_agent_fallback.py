import json
from pathlib import Path

from mcp_rules_assistant.dev_agent import compute_status


def test_compute_status_uses_dashboard_fallback_when_no_coverage(
    tmp_path: Path,
) -> None:
    # Prepare previous dashboard status with coverage info, but no coverage.xml
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    prev = {
        "coverage": {
            "weak": [],
            "groups": [
                {
                    "prefix": "other",
                    "coverage": 0.99,
                    "threshold": 0.96,
                    "weak_count": 0,
                    "files_count": 1,
                }
            ],
            "near": [],
            "count": 1,
        }
    }
    (dash / "status.json").write_text(
        json.dumps(prev, ensure_ascii=False), encoding="utf-8"
    )

    out = compute_status(tmp_path)
    cov = out.get("coverage", {})
    assert isinstance(cov, dict)
    # Should reflect previous count from fallback
    assert int(cov.get("count", 0)) == 1
