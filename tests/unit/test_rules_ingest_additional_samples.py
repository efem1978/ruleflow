from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_rules_ingest_additional_phrases(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    doc = tmp_path / "rules_more.md"
    # 混合语句：上限/区间/口语百分比/安全与容器
    doc.write_text(
        "\n".join(
            [
                "- 覆盖率 九成五",  # 0.95
                "- 核心 不少于 96.2%",  # 0.962
                "- 核心 覆盖率 十成",  # 1.0
                "- 覆盖率 介于 96% 和 99% 之间",  # 区间：min=0.96, 上限=0.99（建议）
                "- SAST 严格/semgrep",  # security.sast_strict
                "- Docker/容器化/devcontainer",  # container.required
            ]
        ),
        encoding="utf-8",
    )
    out = srv._call_tool("rules.ingest", {"paths": [str(doc)]})
    assert out.get("files") == 1
    # rules.validate should succeed afterwards
    _ = srv._call_tool("rules.validate", {})
