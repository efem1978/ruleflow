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


def test_summarize_marks_weak_and_sets_delta(tmp_path: Path) -> None:
    xml = tmp_path / "coverage.xml"
    _write_cov_xml(
        xml,
        [
            {"filename": "foo.py", "line-rate": "0.50", "lines-valid": "10", "lines-covered": "5"},
        ],
    )
    out = cs.summarize(project_root=tmp_path, coverage_xml="coverage.xml", policy=None, min_module=0.96)
    assert out.get("ok") is True
    weak = out.get("weak") or []
    assert isinstance(weak, list) and len(weak) == 1
    w0 = weak[0]
    assert w0.get("file") == "foo.py"
    assert w0.get("threshold") == 0.96
    assert abs(float(w0.get("delta", 0.0)) - (0.96 - 0.50)) < 1e-9


def test_summarize_near_within_window(tmp_path: Path) -> None:
    xml = tmp_path / "coverage.xml"
    _write_cov_xml(
        xml,
        [
            {"filename": "bar.py", "line-rate": "0.970"},
            {"filename": "baz.py", "line-rate": "0.990"},
        ],
    )
    out = cs.summarize_near(project_root=tmp_path, coverage_xml="coverage.xml", policy=None, min_module=0.96, within=0.03, top=50)
    assert out.get("ok") is True
    near = out.get("near") or []
    files = {str(it.get("file")) for it in near}
    assert "bar.py" in files
    # 0.99 - 0.96 == 0.03, inclusive window, so also near
    assert "baz.py" in files
