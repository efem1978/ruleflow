from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.coverage_summary import (
    summarize,
    summarize_groups,
    summarize_near,
    summarize_tree,
)


def _xml(classes: list[str]) -> str:
    return (
        "<coverage>\n<packages><package><classes>\n"
        + "\n".join(classes)
        + "\n"
        + "</classes></package></packages>\n</coverage>\n"
    )


def test_summarize_no_policy_path(tmp_path: Path) -> None:
    # one file below default threshold → weak
    c = '<class filename="pkg/a.py" line-rate="0.89" lines-valid="100" lines-covered="89"/>'
    (tmp_path / "coverage.xml").write_text(_xml([c]), encoding="utf-8")
    out = summarize(project_root=tmp_path, policy=None, min_module=0.90)
    assert out.get("ok") is True and out.get("weak")
    w = out.get("weak")[0]
    assert w.get("file") == "pkg/a.py" and abs(float(w.get("threshold")) - 0.90) < 1e-6


def test_summarize_missing_xml_and_groups_missing(tmp_path: Path) -> None:
    out = summarize(project_root=tmp_path)
    assert out.get("ok") is False and "not found" in str(out.get("message", ""))
    out2 = summarize_groups(project_root=tmp_path)
    assert out2.get("ok") is False and "not found" in str(out2.get("message", ""))


def test_summarize_near_within_and_top(tmp_path: Path) -> None:
    c1 = '<class filename="a.py" line-rate="0.952" lines-valid="100" lines-covered="95"/>'
    c2 = '<class filename="b.py" line-rate="0.991" lines-valid="100" lines-covered="99"/>'
    (tmp_path / "coverage.xml").write_text(_xml([c1, c2]), encoding="utf-8")
    out = summarize_near(
        project_root=tmp_path, policy=None, min_module=0.95, within=0.05, top=1,
    )
    assert out.get("ok") is True
    near = out.get("near") or []
    # only top=1 should be returned, and both are >= threshold
    assert len(near) == 1 and near[0].get("file") in {"a.py", "b.py"}


def test_summarize_tree_base_not_ok(tmp_path: Path) -> None:
    out = summarize_tree(project_root=tmp_path)
    assert out.get("ok") is False and "not found" in str(out.get("message", ""))


def test_summarize_with_bad_coverage_policy(monkeypatch, tmp_path: Path) -> None:
    # stub classes to include non-numeric coverage → comparison raises, hits except path (144-145)
    import mcp_rules_assistant.coverage_summary as cs

    (tmp_path / "coverage.xml").write_text("<coverage/>", encoding="utf-8")
    monkeypatch.setattr(
        cs,
        "_read_classes_with_cache",
        lambda root, xml: [
            {"file": "x.py", "coverage": "bad"},
        ],
    )
    out = summarize(project_root=tmp_path, policy={"x": 0.9}, min_module=0.9)
    assert out.get("ok") is True and out.get("count") == 1


def test_summarize_with_bad_coverage_no_policy(monkeypatch, tmp_path: Path) -> None:
    # no policy path, non-numeric coverage triggers except (158-159)
    import mcp_rules_assistant.coverage_summary as cs

    (tmp_path / "coverage.xml").write_text("<coverage/>", encoding="utf-8")
    monkeypatch.setattr(
        cs,
        "_read_classes_with_cache",
        lambda root, xml: [
            {"file": "y.py", "coverage": {"oops": 1}},
        ],
    )
    out = summarize(project_root=tmp_path, policy=None, min_module=0.9)
    assert out.get("ok") is True and out.get("count") == 1


def test_summarize_groups_bad_line_counts(monkeypatch, tmp_path: Path) -> None:
    # bad lines_valid/covered → triggers except (237-239) and fallback to file weight
    import mcp_rules_assistant.coverage_summary as cs

    (tmp_path / "coverage.xml").write_text("<coverage/>", encoding="utf-8")
    monkeypatch.setattr(
        cs,
        "_read_classes_with_cache",
        lambda root, xml: [
            {
                "file": "a.py",
                "coverage": 0.80,
                "lines_valid": "bad",
                "lines_covered": "bad",
            },
            {
                "file": "b.py",
                "coverage": 0.99,
                "lines_valid": None,
                "lines_covered": None,
            },
        ],
    )
    out = summarize_groups(project_root=tmp_path, policy=None, min_module=0.9)
    assert out.get("ok") is True and out.get("groups")
