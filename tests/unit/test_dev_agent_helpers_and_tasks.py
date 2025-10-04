from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.dev_agent as DA


def test_collect_tasks_counts_includes_docs_and_readme(tmp_path: Path) -> None:
    # plan with none, docs/readme with checkboxes and Next Actions
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".mcp/plan.md").write_text("# plan\n", encoding="utf-8")
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/x.md").write_text("- [x] done\n- [ ] todo\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("- [ ] readme-todo\n", encoding="utf-8")
    done, pending, pend_list, done_list = DA._collect_tasks_counts(  # type: ignore[attr-defined]
        tmp_path, "# Next Actions\n- a\n- b\n", include_docs=True,
    )
    assert pending >= 1 and done >= 1
    assert any("todo" in p for p in pend_list)


def test_module_wrappers_run_and_git_changed_files(tmp_path: Path, monkeypatch) -> None:
    # Monkeypatch to avoid launching real pytest and git
    monkeypatch.setattr(
        DA,
        "run_cmd",
        lambda *a, **k: type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
    )
    # No changed files -> runs full
    out = DA._run_impacted_or_full(tmp_path, cycle_idx=1)  # type: ignore[attr-defined]
    assert out.get("mode") in ("full", "quick")
    files = DA._git_changed_files(tmp_path)  # type: ignore[attr-defined]
    assert isinstance(files, list)
    # Public wrappers
    out2 = DA.run_impacted_or_full(tmp_path, cycle_idx=2)
    assert out2.get("mode") in ("full", "quick")
