from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def test_development_main_anchors_exist() -> None:
    p = ROOT / "DEVELOPMENT.md"
    text = read(p)
    for key in [
        "开发指南总览",
        "快速索引",
        "环境与运行",
        "TDD 逐层推进计划",
        "提交与门禁",
        "无人值守",
        "文档维护与同步",
    ]:
        assert key in text, f"missing anchor in DEVELOPMENT.md: {key}"


def test_docker_dev_no_ui_and_has_status_files() -> None:
    p = ROOT / "docs" / "DOCKER_DEV.md"
    text = read(p)
    assert ".mcp/dashboard/status.json" in text
    # ensure no stale UI hints
    # 精确禁止旧版前端静态资源/服务端口，不误伤 status.json
    banned = ["localhost:9000", "--serve", "index.html", "status.js"]
    for b in banned:
        if b == "status.js":
            assert (
                re.search(r"(^|[^a-zA-Z0-9_])status\.js([^a-zA-Z0-9_]|$)", text) is None
            ), f"banned pattern in DOCKER_DEV.md: {b}"
        else:
            assert b not in text, f"banned pattern in DOCKER_DEV.md: {b}"
    # compose naming
    assert "compose.yml" in text
    assert "docker-compose.yml" not in text


def test_readme_links_to_development() -> None:
    text = read(ROOT / "README.md")
    assert "DEVELOPMENT.md" in text


def test_ai_dev_guide_points_to_development() -> None:
    text = read(ROOT / "docs" / "AI_DEVELOPER_GUIDE.md")
    assert "DEVELOPMENT.md" in text


def test_hooks_mentions_vscode_required() -> None:
    text = read(ROOT / "docs" / "HOOKS.md")
    assert "VS Code 无头测试（必跑项）" in text


def test_repo_docs_no_stale_compose_or_dashboard_patterns() -> None:
    # scan key docs for banned patterns
    docs = [ROOT / "DEVELOPMENT.md", *(ROOT / "docs").glob("*.md"), ROOT / "README.md"]
    banned = [
        "docker-compose.yml",
        "--serve",
        "localhost:9000",
        "status.js",
        "index.html",
    ]
    for d in docs:
        t = read(d)
        for b in banned:
            if b == "status.js":
                assert (
                    re.search(r"(^|[^a-zA-Z0-9_])status\.js([^a-zA-Z0-9_]|$)", t)
                    is None
                ), f"banned pattern in {d}: {b}"
            else:
                assert b not in t, f"banned pattern in {d}: {b}"
