"""Test CLI doctor command to achieve 98% coverage for cli.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock


from mcp_rules_assistant.cli import doctor


def test_doctor_no_venv_no_fix(tmp_path: Path, monkeypatch, capsys):
    """Test doctor when venv doesn't exist and fix=False."""
    monkeypatch.chdir(tmp_path)
    
    # Run doctor without fix
    doctor(verbose=False, fix=False, clear_fake=False)
    
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    
    # Should report venv doesn't exist
    assert result["venv"]["exists"] is False
    assert result["ok"] is False


def test_doctor_with_venv_creation(tmp_path: Path, monkeypatch, capsys):
    """Test doctor creates venv when fix=True."""
    monkeypatch.chdir(tmp_path)
    
    # Mock subprocess to avoid actual venv creation
    original_run = subprocess.run
    run_calls = []
    
    def mock_run(*args, **kwargs):
        run_calls.append((args, kwargs))
        # Simulate successful venv creation
        if "venv" in str(args[0]):
            venv_dir = tmp_path / ".mcp" / "venv"
            venv_dir.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                (venv_dir / "Scripts").mkdir(exist_ok=True)
                (venv_dir / "Scripts" / "python.exe").touch()
            else:
                (venv_dir / "bin").mkdir(exist_ok=True)
                (venv_dir / "bin" / "python").touch()
            return mock.Mock(returncode=0, stdout="", stderr="")
        # Mock import check - fail first to trigger install
        if "import mcp_rules_assistant" in str(args[0]):
            return mock.Mock(returncode=1, stdout="", stderr="import error")
        # Mock pip install
        if "pip" in str(args[0]) and "install" in str(args[0]):
            return mock.Mock(returncode=0, stdout="", stderr="")
        # Mock diagnose
        if "diagnose" in str(args[0]):
            diag_output = json.dumps({"status": "ok"})
            return mock.Mock(returncode=0, stdout=diag_output, stderr="")
        return original_run(*args, **kwargs)
    
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Run doctor with fix
    doctor(verbose=True, fix=True, clear_fake=False)
    
    captured = capsys.readouterr()
    # Extract JSON from last line (verbose mode adds log lines)
    json_line = captured.out.strip().split('\n')[-1]
    result = json.loads(json_line)
    
    # Should have created venv
    assert "create_venv" in result["actions"]
    assert result["venv"]["exists"] is True


def test_doctor_existing_venv_import_ok(tmp_path: Path, monkeypatch, capsys):
    """Test doctor with existing venv and successful import."""
    monkeypatch.chdir(tmp_path)
    
    # Create fake venv
    venv_dir = tmp_path / ".mcp" / "venv"
    if sys.platform == "win32":
        venv_dir.mkdir(parents=True, exist_ok=True)
        (venv_dir / "Scripts").mkdir(exist_ok=True)
        (venv_dir / "Scripts" / "python.exe").touch()
    else:
        venv_dir.mkdir(parents=True, exist_ok=True)
        (venv_dir / "bin").mkdir(exist_ok=True)
        (venv_dir / "bin" / "python").touch()
    
    # Mock subprocess
    def mock_run(*args, **kwargs):
        # Mock successful import
        if "import mcp_rules_assistant" in str(args[0]):
            return mock.Mock(returncode=0, stdout="ok\n", stderr="")
        # Mock pip upgrade
        if "pip" in str(args[0]) and "-U" in str(args[0]):
            return mock.Mock(returncode=0, stdout="", stderr="")
        # Mock diagnose
        if "diagnose" in str(args[0]):
            diag_output = json.dumps({"healthy": True})
            return mock.Mock(returncode=0, stdout=diag_output, stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")
    
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Run doctor
    doctor(verbose=False, fix=True, clear_fake=False)
    
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    
    # Should report ok since import succeeded
    assert result["venv"]["exists"] is True
    # Should not need to install
    assert "pip_install_editable" not in result["actions"]


def test_doctor_clear_fake_mode(tmp_path: Path, monkeypatch, capsys):
    """Test doctor clears fake mode file."""
    monkeypatch.chdir(tmp_path)
    
    # Create fake mode file
    fake_file = tmp_path / ".mcp" / "dashboard" / "fake_mode"
    fake_file.parent.mkdir(parents=True, exist_ok=True)
    fake_file.touch()
    
    assert fake_file.exists()
    
    # Mock subprocess
    def mock_run(*args, **kwargs):
        if "diagnose" in str(args[0]):
            return mock.Mock(returncode=0, stdout="{}", stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")
    
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Run doctor with clear_fake
    doctor(verbose=False, fix=False, clear_fake=True)
    
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    
    # Should have cleared fake mode
    assert "clear_fake_mode" in result["actions"]
    assert not fake_file.exists()


def test_doctor_exception_handling(tmp_path: Path, monkeypatch, capsys):
    """Test doctor handles exceptions gracefully."""
    monkeypatch.chdir(tmp_path)
    
    # Mock subprocess to raise exception
    def mock_run_error(*args, **kwargs):
        if "venv" in str(args[0]):
            raise RuntimeError("Failed to create venv")
        return mock.Mock(returncode=1, stdout="", stderr="")
    
    monkeypatch.setattr(subprocess, "run", mock_run_error)
    
    # Run doctor - should not crash
    doctor(verbose=False, fix=True, clear_fake=False)
    
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    
    # Should report not ok due to exception
    assert result["ok"] is False
    # Should have error in actions
    assert any("error:" in str(a) for a in result["actions"])


def test_doctor_diagnose_failure(tmp_path: Path, monkeypatch, capsys):
    """Test doctor when diagnose command fails."""
    monkeypatch.chdir(tmp_path)
    
    # Create fake venv
    venv_dir = tmp_path / ".mcp" / "venv"
    venv_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        (venv_dir / "Scripts").mkdir(exist_ok=True)
        (venv_dir / "Scripts" / "python.exe").touch()
    else:
        (venv_dir / "bin").mkdir(exist_ok=True)
        (venv_dir / "bin" / "python").touch()
    
    # Mock subprocess
    def mock_run(*args, **kwargs):
        # Import check succeeds
        if "import mcp_rules_assistant" in str(args[0]):
            return mock.Mock(returncode=0, stdout="ok\n", stderr="")
        # Diagnose fails
        if "diagnose" in str(args[0]):
            return mock.Mock(returncode=1, stdout="", stderr="error")
        return mock.Mock(returncode=0, stdout="", stderr="")
    
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Run doctor
    doctor(verbose=False, fix=False, clear_fake=False)
    
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    
    # Should report not ok due to diagnose failure
    assert result["ok"] is False


def test_doctor_diagnose_json_parse_error(tmp_path: Path, monkeypatch, capsys):
    """Test doctor when diagnose returns invalid JSON."""
    monkeypatch.chdir(tmp_path)
    
    # Create fake venv
    venv_dir = tmp_path / ".mcp" / "venv"
    venv_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        (venv_dir / "Scripts").mkdir(exist_ok=True)
        (venv_dir / "Scripts" / "python.exe").touch()
    else:
        (venv_dir / "bin").mkdir(exist_ok=True)
        (venv_dir / "bin" / "python").touch()
    
    # Mock subprocess
    def mock_run(*args, **kwargs):
        # Import check succeeds
        if "import mcp_rules_assistant" in str(args[0]):
            return mock.Mock(returncode=0, stdout="ok\n", stderr="")
        # Diagnose returns invalid JSON
        if "diagnose" in str(args[0]):
            return mock.Mock(returncode=0, stdout="invalid {json}", stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")
    
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Run doctor - should handle JSON parse error
    doctor(verbose=False, fix=False, clear_fake=False)
    
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    
    # Should report not ok and have diagnose_error
    assert result["ok"] is False
    assert any("diagnose_error:" in str(a) for a in result["actions"])


def test_doctor_verbose_logging(tmp_path: Path, monkeypatch, capsys):
    """Test doctor verbose mode outputs log messages."""
    monkeypatch.chdir(tmp_path)
    
    # Mock subprocess
    def mock_run(*args, **kwargs):
        if "diagnose" in str(args[0]):
            return mock.Mock(returncode=0, stdout="{}", stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")
    
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Run with verbose
    doctor(verbose=True, fix=False, clear_fake=False)
    
    captured = capsys.readouterr()
    # Should have verbose output (checking stderr or stdout depending on rprint)
    # At minimum, should have JSON output
    assert captured.out.strip()
    result = json.loads(captured.out.strip().split('\n')[-1])
    assert "venv" in result
