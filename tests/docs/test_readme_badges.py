from __future__ import annotations

from pathlib import Path


def test_readme_contains_ci_and_codecov_badges() -> None:
    p = Path("README.md")
    text = p.read_text(encoding="utf-8")
    assert "img.shields.io/github/actions/workflow/status" in text
    assert "codecov.io" in text and "badge.svg" in text
