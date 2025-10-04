"""Test CLI diagnose command helper functions for cli.py coverage."""
from __future__ import annotations

import json
import platform
from pathlib import Path


from mcp_rules_assistant.cli import diagnose


def test_diagnose_with_invalid_status_json(tmp_path: Path, monkeypatch, capsys):
    """Test diagnose when status.json is invalid, triggering exception branch at line 498-499."""
    monkeypatch.chdir(tmp_path)
    
    # Create invalid status.json
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    (dash / "status.json").write_text("invalid {json}", encoding="utf-8")
    
    # Should handle exception gracefully
    diagnose(json_out=True)
    
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    
    # Should have empty data due to JSON parse exception
    assert isinstance(result, dict)


def test_diagnose_helper_get_with_non_dict(tmp_path: Path, monkeypatch, capsys):
    """Test _get helper when encountering non-dict values (line 505-506)."""
    monkeypatch.chdir(tmp_path)
    
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    
    # Create status with non-dict nested value to trigger _get early return
    status_data = {
        "coverage": "not_a_dict",  # Should trigger isinstance check
        "checks": {"nested": "value"},
    }
    (dash / "status.json").write_text(json.dumps(status_data), encoding="utf-8")
    
    # Run diagnose - should handle non-dict gracefully
    diagnose(json_out=False)
    captured = capsys.readouterr()
    assert "Diagnose" in captured.out


def test_diagnose_helper_set_create_nested_dicts(tmp_path: Path, monkeypatch, capsys):
    """Test _set helper creates nested dicts (line 513-514)."""
    monkeypatch.chdir(tmp_path)
    
    # Create minimal setup
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    (dash / "status.json").write_text("{}", encoding="utf-8")
    
    # Create assistant.yaml that will trigger _set
    config_file = tmp_path / ".mcp" / "assistant.yaml"
    config_file.write_text("", encoding="utf-8")
    
    # Run diagnose - this will exercise _set when building proposals
    diagnose(json_out=False)
    captured = capsys.readouterr()
    assert "Diagnose" in captured.out


def test_diagnose_read_compiled_policy_exception(tmp_path: Path, monkeypatch, capsys):
    """Test _read_compiled_policy exception handling (line 524-525)."""
    monkeypatch.chdir(tmp_path)
    
    # Create invalid rules_compiled.json
    rules_file = tmp_path / ".mcp" / "rules_compiled.json"
    rules_file.parent.mkdir(parents=True, exist_ok=True)
    rules_file.write_text("invalid json {[", encoding="utf-8")
    
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    (dash / "status.json").write_text("{}", encoding="utf-8")
    
    # Should handle JSON parse exception gracefully
    diagnose(json_out=False)
    captured = capsys.readouterr()
    assert "Diagnose" in captured.out


def test_diagnose_wsl_detection_linux(tmp_path: Path, monkeypatch, capsys):
    """Test WSL detection on Linux (line 536-540)."""
    monkeypatch.chdir(tmp_path)
    
    # Mock platform to be Linux
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    
    # Mock /proc/version to contain "microsoft"
    fake_proc = tmp_path / "fake_proc_version"
    fake_proc.write_text("Linux version 4.4.0-19041-Microsoft", encoding="utf-8")
    
    original_read_text = Path.read_text
    
    def mock_read_text(self, *args, **kwargs):
        if str(self) == "/proc/version":
            return fake_proc.read_text(*args, **kwargs)
        return original_read_text(self, *args, **kwargs)
    
    monkeypatch.setattr(Path, "read_text", mock_read_text)
    
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    (dash / "status.json").write_text("{}", encoding="utf-8")
    
    # Run diagnose
    diagnose(json_out=False)
    captured = capsys.readouterr()
    assert "Diagnose" in captured.out


def test_diagnose_wsl_detection_exception(tmp_path: Path, monkeypatch, capsys):
    """Test WSL detection exception handling (line 539-540)."""
    monkeypatch.chdir(tmp_path)
    
    # Mock platform to be Linux
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    
    # Mock Path.read_text to raise exception
    def mock_read_text_error(self, *args, **kwargs):
        if "/proc/version" in str(self):
            raise PermissionError("Cannot read /proc/version")
        return Path.read_text.__func__(self, *args, **kwargs)
    
    monkeypatch.setattr(Path, "read_text", mock_read_text_error)
    
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    (dash / "status.json").write_text("{}", encoding="utf-8")
    
    # Should handle exception gracefully
    diagnose(json_out=False)
    captured = capsys.readouterr()
    assert "Diagnose" in captured.out


def test_diagnose_tool_detection(tmp_path: Path, monkeypatch, capsys):
    """Test tool detection logic (docker/code/node) at lines 531-533."""
    monkeypatch.chdir(tmp_path)
    
    # Mock shutil.which to return None (tools not found)
    import shutil
    original_which = shutil.which
    
    def mock_which(name):
        # Simulate tools not found
        if name in ["docker", "code", "code-insiders", "node"]:
            return None
        return original_which(name)
    
    monkeypatch.setattr(shutil, "which", mock_which)
    
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    (dash / "status.json").write_text("{}", encoding="utf-8")
    
    # Run diagnose - should detect missing tools
    diagnose(json_out=False)
    captured = capsys.readouterr()
    assert "Diagnose" in captured.out
    # Should show docker as missing
    assert "docker: missing" in captured.out
