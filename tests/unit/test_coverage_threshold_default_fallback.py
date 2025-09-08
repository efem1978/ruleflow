from __future__ import annotations

import mcp_rules_assistant.coverage_summary as cs


def test_threshold_default_parse_error_fallback_to_0_9() -> None:
    # default cannot be converted to float → fallback to 0.9
    th = cs._threshold_for_file("x.py", policy=None, default="bad")  # type: ignore[arg-type]
    assert abs(th - 0.9) < 1e-9
