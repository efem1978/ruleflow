from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import checks


def test_module_import_candidates(tmp_path: Path) -> None:
    proj = tmp_path
    file = proj / "mcp_rules_assistant" / "mod" / "foo.py"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("x=1", encoding="utf-8")
    out = checks._module_import_candidates(proj, file)
    assert out == ["mcp_rules_assistant.mod.foo"]


def test_build_and_load_test_index(tmp_path: Path) -> None:
    proj = tmp_path
    tests_dir = proj / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    (proj / "pkg").mkdir(parents=True, exist_ok=True)
    (proj / "pkg" / "util.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    # a test imports pkg.util, should be indexed
    (tests_dir / "test_util.py").write_text("from pkg import util\n", encoding="utf-8")

    idx = checks.build_test_index(proj)
    assert any("test_util.py" in v[0] for k, v in idx.items() if k.startswith("pkg"))

    # load should reuse cache, unless signature changes
    idx2 = checks.load_test_index(proj)
    assert idx2


def test_run_lint_skips_on_non_python_files(tmp_path: Path) -> None:
    f = tmp_path / "README.txt"
    f.write_text("hello", encoding="utf-8")
    res = checks.run_lint([f], cwd=tmp_path)
    assert res.get("skipped") is True
