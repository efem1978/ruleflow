from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.coverage_summary as cs


def test_summarize_sort_key_guard(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "coverage.xml").write_text("<coverage/>", encoding="utf-8")
    # Stub classes: one file below threshold to produce a weak entry
    monkeypatch.setattr(
        cs,
        "_read_classes_with_cache",
        lambda root, xml: [
            {"file": "a.py", "coverage": 0.5, "lines_valid": 10, "lines_covered": 5},
        ],
    )
    import builtins

    orig_sorted = builtins.sorted

    def sorted_wrap(iterable, key=None, **kwargs):  # type: ignore[override]
        # call key once with bad delta to trigger except in sort_key
        if key is not None:
            try:
                key({"delta": {"bad": 1}})  # not convertible to float
            except Exception:
                pass
        return orig_sorted(iterable, key=key, **kwargs)

    monkeypatch.setattr(builtins, "sorted", sorted_wrap)
    out = cs.summarize(project_root=tmp_path, policy={"a.py": 0.9}, min_module=0.9)
    assert out.get("ok") is True and isinstance(out.get("weak"), list)


def test_summarize_groups_key_cov_guard(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "coverage.xml").write_text("<coverage/>", encoding="utf-8")
    # Stub classes for groups
    monkeypatch.setattr(
        cs,
        "_read_classes_with_cache",
        lambda root, xml: [
            {"file": "a.py", "coverage": 0.95, "lines_valid": 10, "lines_covered": 10},
            {"file": "b.py", "coverage": 0.91, "lines_valid": 10, "lines_covered": 9},
        ],
    )
    import builtins

    orig_sorted = builtins.sorted

    def sorted_wrap(iterable, key=None, **kwargs):  # type: ignore[override]
        if key is not None:
            try:
                key({"coverage": {"bad": 1}})  # trigger except in _key_cov
            except Exception:
                pass
        return orig_sorted(iterable, key=key, **kwargs)

    monkeypatch.setattr(builtins, "sorted", sorted_wrap)
    out = cs.summarize_groups(project_root=tmp_path, policy=None, min_module=0.92)
    assert out.get("ok") is True and isinstance(out.get("groups"), list)


def test_summarize_near_key_delta_guard(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "coverage.xml").write_text("<coverage/>", encoding="utf-8")
    # Stub classes for near
    monkeypatch.setattr(
        cs,
        "_read_classes_with_cache",
        lambda root, xml: [
            {"file": "a.py", "coverage": 0.95, "lines_valid": 10, "lines_covered": 10},
            {"file": "b.py", "coverage": 0.951, "lines_valid": 10, "lines_covered": 10},
        ],
    )
    import builtins

    orig_sorted = builtins.sorted

    def sorted_wrap(iterable, key=None, **kwargs):  # type: ignore[override]
        if key is not None:
            try:
                key({"delta_up": {"bad": 1}})  # trigger except in _key_delta
            except Exception:
                pass
        return orig_sorted(iterable, key=key, **kwargs)

    monkeypatch.setattr(builtins, "sorted", sorted_wrap)
    out = cs.summarize_near(
        project_root=tmp_path, policy=None, min_module=0.95, within=0.01, top=5,
    )
    assert out.get("ok") is True and isinstance(out.get("near"), list)
