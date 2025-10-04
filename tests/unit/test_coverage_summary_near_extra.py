from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.coverage_summary as cs


def _cov_one(tmp: Path, fname: str, cov: float) -> None:
    xml = f"""
    <coverage line-rate="1.0" branch-rate="0" version="1" timestamp="0">
      <packages><package name="p"><classes>
        <class filename="{fname}" line-rate="{cov}" lines-valid="10" lines-covered="{int(round(cov*10))}"/>
      </classes></package></packages>
    </coverage>
    """.strip()
    (tmp / "coverage.xml").write_text(xml, encoding="utf-8")


def test_near_includes_when_gap_within(tmp_path: Path) -> None:
    # threshold 0.96; file coverage 0.971 → gap 0.011 <= within 0.02 → included
    _cov_one(tmp_path, "a.py", 0.971)
    out = cs.summarize_near(
        project_root=tmp_path,
        coverage_xml="coverage.xml",
        policy={"a.py": 0.96},
        min_module=0.90,
        within=0.02,
        top=10,
    )
    near = out.get("near") or []
    assert any(str(it.get("file")) == "a.py" for it in near)


def test_near_excludes_when_gap_exceeds(tmp_path: Path) -> None:
    _cov_one(tmp_path, "b.py", 0.98)
    out = cs.summarize_near(
        project_root=tmp_path,
        coverage_xml="coverage.xml",
        policy={"b.py": 0.95},
        min_module=0.90,
        within=0.02,
        top=10,
    )
    near = out.get("near") or []
    # gap = 0.03 > within 0.02 → not included
    assert all(str(it.get("file")) != "b.py" for it in near)
