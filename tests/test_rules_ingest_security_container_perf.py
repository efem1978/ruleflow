from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import rules_ingest as ri


def test_sast_devcontainer_perf_and_vcs_flags(tmp_path: Path) -> None:
    d = tmp_path / "r.txt"
    d.write_text(
        "\n".join(
            [
                "- SAST 严格",
                "- 使用 devcontainer 进行开发",
                "- 响应时间 < 200ms",
                "- conventional commits",
                "- 分支策略 采用 trunk-based",
                "- 密钥扫描 detect-secrets",
                "- 使用 Docker 部署",
                "- 镜像基线 rootless",
            ],
        ),
        encoding="utf-8",
    )
    res = ri.ingest([str(d)], project_root=tmp_path)
    pol = (res.get("compiled") or {}).get("policy") or {}
    assert pol.get("security.sast_strict") is True
    assert pol.get("container.required") is True
    assert pol.get("container.policy.baseline") is True
    assert pol.get("security.secrets_scan") is True
    assert pol.get("vcs.conventional_commits") is True
    assert pol.get("vcs.branch_policy") is True
    assert int(pol.get("perf.budget_ms") or 0) == 200
