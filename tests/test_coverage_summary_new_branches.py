from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.coverage_summary as cs


def _write_min_cov_xml(p: Path, *, line_rate: str | None = "1.0", lv: str | None = None, lc: str | None = None) -> None:
    # Create a minimal Cobertura-like coverage file with one class entry
    attrs = []
    if line_rate is not None:
        attrs.append(f'line-rate="{line_rate}"')
    if lv is not None:
        attrs.append(f'lines-valid="{lv}"')
    if lc is not None:
        attrs.append(f'lines-covered="{lc}"')
    attr_str = " ".join(attrs)
    xml = f"""
    <coverage>
      <packages>
        <package name=".">
          <classes>
            <class name="x" filename="file.py" {attr_str} />
          </classes>
        </package>
      </packages>
    </coverage>
    """.strip()
    p.write_text(xml, encoding="utf-8")


def test_cache_files_shape_is_list_is_ignored(tmp_path: Path) -> None:
    # Pre-create a cache file where "files" is not a dict to hit the else branch
    cache = tmp_path / ".mcp/coverage_cache.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("{""files"": []}", encoding="utf-8")
    cov = tmp_path / "coverage.xml"
    _write_min_cov_xml(cov)
    r = cs.summarize(project_root=tmp_path)
    assert r.get("ok") is True


def test_lines_valid_and_covered_bad_values_do_not_crash(tmp_path: Path) -> None:
    # Force the path that attempts int(float(lines_valid/covered)) and swallows errors
    cov = tmp_path / "coverage.xml"
    _write_min_cov_xml(cov, line_rate=None, lv="bad", lc="bad")
    r = cs.summarize(project_root=tmp_path)
    assert r.get("ok") is True


def test_policy_delta_float_failure_path(tmp_path: Path) -> None:
    # Coverage object that cannot be converted to float during delta computation
    class Bad:
        def __lt__(self, other):
            return True

        def __float__(self):  # pragma: no cover - invoked indirectly
            raise ValueError("bad")

    cov = tmp_path / "coverage.xml"
    _write_min_cov_xml(cov)

    # Patch reader to return a Bad coverage object; use policy to go through policy branch
    def fake_read(project_root, coverage_xml):
        return [{"file": "pref/file.py", "coverage": Bad()}]

    orig = cs._read_classes_with_cache
    cs._read_classes_with_cache = fake_read  # type: ignore[assignment]
    try:
        r = cs.summarize(project_root=tmp_path, policy={"pref/": 0.95}, min_module=0.9)
        assert r.get("ok") is True
    finally:
        cs._read_classes_with_cache = orig  # type: ignore[assignment]


def test_groups_and_near_cover(tmp_path: Path) -> None:
    # One weak file (below default 0.90) + one near file (>=0.95 but within 0.02)
    xml = (
        "<coverage>\n"
        "  <packages><package name='.'><classes>\n"
        "    <class name='a' filename='a.py' line-rate='0.80' lines-valid='10' lines-covered='8'/>\n"
        "    <class name='b' filename='b.py' line-rate='0.96' lines-valid='50' lines-covered='48'/>\n"
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    (tmp_path / "coverage.xml").write_text(xml, encoding="utf-8")
    g = cs.summarize_groups(project_root=tmp_path, min_module=0.9)
    assert g.get("ok") is True
    near = cs.summarize_near(project_root=tmp_path, min_module=0.95, within=0.02)
    assert near.get("ok") is True and near.get("near")
