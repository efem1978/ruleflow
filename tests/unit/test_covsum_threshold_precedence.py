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


def test_threshold_suffix_overrides_prefix_and_default(tmp_path: Path) -> None:
    xml = tmp_path / "coverage.xml"
    _write_cov_xml(
        xml,
        [
            {"filename": "pkg/cli.py", "line-rate": "0.90"},
        ],
    )
    policy = {
        "pkg/": 0.80,  # prefix policy (less specific)
        "cli.py": 0.99,  # suffix policy (more specific, should win)
    }
    out = cs.summarize(
        project_root=tmp_path,
        coverage_xml="coverage.xml",
        policy=policy,
        min_module=0.70,
    )
    weak = out.get("weak") or []
    # Since suffix threshold 0.99 wins, 0.90 becomes weak
    assert isinstance(weak, list) and len(weak) == 1
    w0 = weak[0]
    assert w0.get("file") == "pkg/cli.py"
    assert abs(float(w0.get("threshold", 0.0)) - 0.99) < 1e-9


def test_summarize_groups_weights_missing_lines(tmp_path: Path) -> None:
    # When lines-valid/covered missing, it should weight by 1 file and still compute group cov
    xml = tmp_path / "coverage.xml"
    _write_cov_xml(
        xml,
        [
            {"filename": "core/a.py", "line-rate": "0.80"},
            {"filename": "core/b.py", "line-rate": "1.00"},
            {"filename": "other/c.py", "line-rate": "1.00"},
        ],
    )
    policy = {"core/": 0.90}
    out = cs.summarize_groups(
        project_root=tmp_path,
        coverage_xml="coverage.xml",
        policy=policy,
        min_module=0.75,
    )
    assert out.get("ok") is True
    groups = out.get("groups") or []
    # find core and other
    gmap = {g.get("prefix"): g for g in groups}
    assert "core/" in gmap and "other" in gmap
    # core group: files=2, one weak due to threshold 0.90
    core = gmap["core/"]
    assert int(core.get("files_count", 0)) == 2
    assert int(core.get("weak_count", 0)) == 1
