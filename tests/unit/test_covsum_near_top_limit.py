from pathlib import Path

from mcp_rules_assistant import coverage_summary as cs


def _write_cov_xml(path: Path, classes: list[dict]) -> None:
    lines = [
        "<?xml version='1.0' encoding='UTF-8'?>",
        "<coverage line-rate='0.0' branch-rate='0.0' version='7.5.0'>",
        "  <packages>",
        "    <package name='pkg' line-rate='0.0' branch-rate='0.0'>",
        "      <classes>",
    ]
    for it in classes:
        attrs = []
        for k, v in it.items():
            attrs.append(f"{k}='{v}'")
        lines.append("        <class " + " ".join(attrs) + "/>")
    lines += [
        "      </classes>",
        "    </package>",
        "  </packages>",
        "</coverage>",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def test_near_top_crops_list(tmp_path: Path) -> None:
    xml = tmp_path / "coverage.xml"
    _write_cov_xml(
        xml,
        [
            {"filename": "a.py", "line-rate": "0.970"},
            {"filename": "b.py", "line-rate": "0.971"},
            {"filename": "c.py", "line-rate": "0.972"},
        ],
    )
    out = cs.summarize_near(
        project_root=tmp_path, coverage_xml="coverage.xml", min_module=0.96, top=2,
    )
    lst = out.get("near") or []
    assert len(lst) == 2
