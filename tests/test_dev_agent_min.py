from pathlib import Path

import pytest

from mcp_rules_assistant import dev_agent as da


def test_compute_status_minimal(tmp_path: Path):
    # No coverage.xml, no plan.md -> should still return a well-formed status
    proj = tmp_path
    out = da.compute_status(project_root=proj)
    assert isinstance(out, dict)
    # Top-level keys
    for k in ["plan", "coverage", "progress", "tasks"]:
        assert k in out
    # Coverage section shape
    cov = out["coverage"]
    assert isinstance(cov, dict)
    assert "weak" in cov and isinstance(cov["weak"], list)
    assert "groups" in cov and isinstance(cov["groups"], list)
    assert "near" in cov and isinstance(cov["near"], list)
    assert "min_module" in cov
    assert "count" in cov


def test_run_impacted_or_full_quick_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    proj = tmp_path

    # pretend there are changed files
    monkeypatch.setattr(da, "_git_changed_files", lambda root: [Path(root) / "a.py"])  # type: ignore[arg-type]

    # quick tests return-ok path
    def fake_quick_tests(
        changed: list[Path],
        cwd: Path,
        do_lint: bool = False,
        do_type: bool = False,
        do_quick_tests: bool = False,
    ) -> dict:
        return {"ok": True, "skipped": False}  # type: ignore[return-value]

    monkeypatch.setattr(da.checks, "run_quick_tests", fake_quick_tests)

    out = da.run_impacted_or_full(proj, cycle_idx=1, full_every=5)
    assert out.get("mode") == "quick"
    assert out.get("ok") is True


def test_run_impacted_or_full_full_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    proj = tmp_path

    # force full by making cycle_idx % full_every == 0
    monkeypatch.setattr(da, "_git_changed_files", lambda root: [Path(root) / "a.py"])  # type: ignore[arg-type]

    called = {"n": 0}

    def fake_full(prj: Path) -> dict:
        called["n"] += 1
        return {"ok": True, "code": 0}

    monkeypatch.setattr(da, "_run_tests_with_coverage", fake_full)

    out = da.run_impacted_or_full(proj, cycle_idx=10, full_every=5)
    assert out.get("mode") == "full"
    assert out.get("ok") is True
    assert called["n"] == 1
