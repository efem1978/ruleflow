"""Extra CLI coverage for coverage-export delta exceptions and doctor unlink errors."""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from mcp_rules_assistant.cli import coverage_export, doctor


def test_coverage_export_delta_exception(tmp_path: Path, monkeypatch):
    """Simulate invalid weak entries to trigger delta except (1111-1112)."""
    monkeypatch.chdir(tmp_path)

    # Monkeypatch cov_summary/near/groups to return invalid types for delta
    import mcp_rules_assistant.cli as cli

    def fake_cov_summary(policy=None, min_module=0.9):
        # include one bad entry to trigger delta except, and one good entry to be written
        return {
            "ok": True,
            "weak": [
                {"file": "bad.py", "coverage": "bad", "threshold": 0.9},  # triggers except
                {"file": "good.py", "coverage": 0.50, "threshold": 0.90},   # will be exported
            ],
        }

    def fake_cov_groups(policy=None, min_module=0.9):
        return {"groups": [{"prefix": "m", "coverage": 0.95, "threshold": 0.98, "weak_count": 1, "files_count": 2}]}

    def fake_cov_near(policy=None, min_module=0.9, within=0.03, top=50):
        return {"near": [{"file": "m.py", "coverage": 0.981, "threshold": 0.98, "delta_up": 0.001}]}

    monkeypatch.setattr(cli, "cov_summary", fake_cov_summary)
    monkeypatch.setattr(cli, "cov_groups", fake_cov_groups)
    monkeypatch.setattr(cli, "cov_near", fake_cov_near)

    # Run export
    # limit to top-1 so that only the good item is written out, while bad triggers delta except during computation
    coverage_export(out_dir=str(tmp_path / ".dash"), weak_top=1, near_top=50, within=None)

    # Files should be generated even with exceptions
    assert (tmp_path / ".dash" / "coverage_summary.json").exists()
    assert (tmp_path / ".dash" / "weak_top.csv").exists()
    assert (tmp_path / ".dash" / "near_top.csv").exists()
    assert (tmp_path / ".dash" / "groups.csv").exists()


def test_doctor_clear_fake_unlink_exception(tmp_path: Path, monkeypatch, capsys):
    """Simulate unlink raising to cover except (1372-1373)."""
    monkeypatch.chdir(tmp_path)

    # Prepare fake mode file
    fake = tmp_path / ".mcp" / "dashboard" / "fake_mode"
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.write_text("1", encoding="utf-8")

    # Patch Path.unlink to raise for our target path
    original_unlink = Path.unlink

    def mock_unlink(self):
        if self == fake:
            raise OSError("mock unlink error")
        return original_unlink(self)

    monkeypatch.setattr(Path, "unlink", mock_unlink)

    # Run doctor
    doctor(verbose=False, fix=False, clear_fake=True)

    # Should not crash and should print JSON
    out = capsys.readouterr().out
    data = json.loads(out)
    assert isinstance(data, dict)
