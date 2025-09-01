from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant import checks


def test_load_test_index_rebuilds_on_change(tmp_path: Path) -> None:
    # Seed a test file and build index
    tdir = tmp_path / 'tests'
    tdir.mkdir(parents=True, exist_ok=True)
    tf = tdir / 'test_sample.py'
    tf.write_text('import alpha\n', encoding='utf-8')
    idx1 = checks.build_test_index(tmp_path)
    assert 'alpha' in idx1
    # Modify file to import a different module
    tf.write_text('import beta\n', encoding='utf-8')
    # load_test_index should detect change and rebuild
    idx2 = checks.load_test_index(tmp_path)
    assert 'beta' in idx2
    # no strict guarantee whether alpha remains; at least new mapping exists

