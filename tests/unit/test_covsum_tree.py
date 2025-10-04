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


def test_summarize_tree_shallow_structure_for_weak(tmp_path: Path) -> None:
    xml = tmp_path / "coverage.xml"
    # Both files below threshold 0.98 -> weak; placed under shallow tree up to depth 3
    _write_cov_xml(
        xml,
        [
            {"filename": "a/b/c.py", "line-rate": "0.90"},
            {"filename": "a/d/e.py", "line-rate": "0.95"},
        ],
    )
    out = cs.summarize_tree(
        project_root=tmp_path,
        coverage_xml="coverage.xml",
        policy=None,
        min_module=0.98,
        max_depth=3,
    )
    assert out.get("ok") is True
    tree = out.get("tree", {})
    assert isinstance(tree, dict) and tree.get("name") == "/"
    children = tree.get("children", {})
    assert isinstance(children, dict) and "a" in children
    a = children["a"]
    assert isinstance(a, dict)
    # depth one children should exist
    ach = a.get("children", {})
    assert "b" in ach and "d" in ach
