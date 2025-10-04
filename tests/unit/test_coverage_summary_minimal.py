from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.coverage_summary import (
    summarize,
    summarize_groups,
    summarize_near,
)

MINIMAL_COV = """
<?xml version='1.0' encoding='UTF-8'?>
<coverage version="7.0" timestamp="0" branch-rate="0" line-rate="1.0">
  <packages>
    <package name="mcp_rules_assistant">
      <classes>
        <class filename="mcp_rules_assistant/example.py" line-rate="0.92" lines-valid="100" lines-covered="92"/>
        <class filename="mcp_rules_assistant/core.py" line-rate="0.99" lines-valid="100" lines-covered="99"/>
      </classes>
    </package>
  </packages>
  </coverage>
""".strip()


def test_summaries_with_minimal_xml(tmp_path: Path) -> None:
    (tmp_path / "coverage.xml").write_text(MINIMAL_COV, encoding="utf-8")

    # threshold 0.95 -> example.py 弱项, core.py 非弱项
    s = summarize(project_root=tmp_path, min_module=0.95)
    assert s["ok"] is True and s["count"] == 2
    weak = s.get("weak", [])
    assert any(it.get("file") == "mcp_rules_assistant/example.py" for it in weak)

    # 分组策略：为 core.py 定更高阈值 0.995，仍应通过（非弱项）
    groups = summarize_groups(
        project_root=tmp_path,
        policy={"mcp_rules_assistant/core.py": 0.98},
        min_module=0.95,
    )
    assert groups["ok"] is True
    # near：core.py 距 0.98 只有 0.01，应命中 near（within=0.03）
    near = summarize_near(project_root=tmp_path, policy={"mcp_rules_assistant/": 0.98})
    files = [it.get("file") for it in near.get("near", [])]
    assert "mcp_rules_assistant/core.py" in files
