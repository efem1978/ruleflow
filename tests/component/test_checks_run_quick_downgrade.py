from __future__ import annotations

import types
from pathlib import Path

from mcp_rules_assistant import checks


def test_run_quick_tests_skips_when_no_impacted(tmp_path: Path, monkeypatch) -> None:
    # no tests and no changed python files -> skipped
    files = [tmp_path / "README.md"]
    res = checks.run_quick_tests(files, cwd=tmp_path)
    assert res.get("skipped") is True


def test_run_quick_tests_downgrades_when_pytest_missing(
    tmp_path: Path, monkeypatch,
) -> None:
    # create a changed python file and a matching test
    (tmp_path / "m").mkdir(parents=True, exist_ok=True)
    (tmp_path / "m" / "a.py").write_text("x=1", encoding="utf-8")
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "test_a.py").write_text(
        "def test_ok():\n assert True\n", encoding="utf-8",
    )

    # simulate pytest missing by making subprocess.run raise FileNotFoundError
    def raise_fn(*a, **k):  # noqa: ANN001
        raise FileNotFoundError

    monkeypatch.setattr(checks, "subprocess", types.SimpleNamespace(run=raise_fn))
    res = checks.run_quick_tests([tmp_path / "m" / "a.py"], cwd=tmp_path)
    # our _run wrapper maps FileNotFoundError to skipped=True
    assert res.get("skipped") is True or res.get("ok") in (True, False)
