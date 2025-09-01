from __future__ import annotations

from pathlib import Path

import mcp_rules_assistant.coverage_summary as cs


def test_summarize_groups_with_bad_coverage(monkeypatch, tmp_path: Path) -> None:
    # need a coverage.xml placeholder to pass existence check
    (tmp_path / 'coverage.xml').write_text('<coverage></coverage>', encoding='utf-8')
    def fake_read(project_root, coverage_xml):
        return [{"file": "pkg/a.py", "coverage": "bad", "lines_valid": "20", "lines_covered": "10"}]
    monkeypatch.setattr(cs, '_read_classes_with_cache', fake_read)
    r = cs.summarize_groups(project_root=tmp_path)
    assert r.get('ok') is True


def test_summarize_delta_exception_with_policy_and_bad_coverage(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / 'coverage.xml').write_text('<coverage></coverage>', encoding='utf-8')
    class Bad:
        def __lt__(self, other):
            return True
        def __float__(self):
            raise ValueError('bad')
    def fake_read(project_root, coverage_xml):
        return [{"file": "pref/file.py", "coverage": Bad()}]
    monkeypatch.setattr(cs, '_read_classes_with_cache', fake_read)
    # numeric policy ensures comparison works, but delta float() fails
    r = cs.summarize(project_root=tmp_path, policy={"pref/": 0.95}, min_module=0.9)
    assert r.get('ok') is True


def test_summarize_tree_deeper_nesting(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / 'coverage.xml').write_text('<coverage></coverage>', encoding='utf-8')
    def fake_read(project_root, coverage_xml):
        return [
            {"file": "a/b/c/d.py", "coverage": 0.5},
            {"file": "a/e/f.py", "coverage": 0.4},
        ]
    monkeypatch.setattr(cs, '_read_classes_with_cache', fake_read)
    r = cs.summarize_tree(project_root=tmp_path, min_module=0.9, max_depth=3)
    assert r.get('ok') is True and isinstance(r.get('tree'), dict)


def test_summarize_delta_try_except_with_bad_coverage_object(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / 'coverage.xml').write_text('<coverage></coverage>', encoding='utf-8')
    class Bad:
        def __lt__(self, other):
            return True
        def __float__(self):
            raise ValueError('bad')
    def fake_read(project_root, coverage_xml):
        return [{"file": "x.py", "coverage": Bad()}]
    monkeypatch.setattr(cs, '_read_classes_with_cache', fake_read)
    r = cs.summarize(project_root=tmp_path)
    assert r.get('ok') is True
