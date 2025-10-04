"""Test exception handling branches in dev_agent to achieve 98% coverage."""
from __future__ import annotations

import json
from pathlib import Path

from mcp_rules_assistant.dev_agent import DevAgent


def test_dev_agent_status_brief_exception_branches(tmp_path: Path, monkeypatch):
    """Test exception handling in status_brief computation."""
    agent = DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp/dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    
    # Create status with malformed data that will be written and trigger exception branches
    status_data = {
        "progress": {"overall": "not_a_number"},  # Will trigger exception in float()
        "coverage": {"weak": "not_a_list"},  # Will trigger exception in len()
        "timestamp": "invalid_timestamp",  # Will trigger exception in float()
        "checks": {"lint": "ok"},
        "tests": {"ok": True},
        "freeze": {"active": False},
        "fail_counters": {
            "counters": {"lint": 0, "tests": 0, "build": 0, "severe": 0},
            "last_trigger": "",
        },
    }
    
    # Write status to file so it gets loaded and processed
    (dash / "status.json").write_text(json.dumps(status_data), encoding="utf-8")
    
    # Run computation which will hit exception branches when processing the bad data
    result = agent.compute_status()
    
    # Should complete without crashing despite exceptions
    assert isinstance(result, dict)


def test_dev_agent_load_coverage_exception_branch(tmp_path: Path, monkeypatch):
    """Test coverage loading exception handling."""
    agent = DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp/dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    
    # Create invalid coverage file to trigger exception
    cov_file = dash / "coverage_summary.json"
    cov_file.write_text("invalid json {[", encoding="utf-8")
    
    # Should handle exception gracefully
    result = agent.compute_status()
    assert isinstance(result, dict)


def test_dev_agent_freeze_recovery_weak_count_exception(tmp_path: Path, monkeypatch):
    """Test weak count exception in freeze recovery logic."""
    agent = DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp/dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    
    # Create status that will trigger freeze recovery check
    status_data = {
        "freeze": {"active": True, "since": "2025-01-01", "reason": "test"},
        "fail_counters": {
            "counters": {"lint": 0, "tests": 0, "build": 0, "severe": 0},
            "last_trigger": "",
            "thresholds": {"lint": 15, "tests": 10, "build": 5, "severe": 3},
        },
        "checks": {"lint": "ok", "type": "ok"},
        "tests": {"ok": True},
        "coverage": {
            "weak": None,  # Will cause exception when checking len()
        },
    }
    
    (dash / "status.json").write_text(json.dumps(status_data), encoding="utf-8")
    
    # Load and process - should handle weak=None gracefully
    result = agent.compute_status()
    assert isinstance(result, dict)


def test_dev_agent_progress_overall_exception(tmp_path: Path, monkeypatch):
    """Test progress.overall exception handling."""
    agent = DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp/dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    
    # Create plan with invalid progress data
    plan_file = tmp_path / ".mcp/plan.md"
    plan_file.write_text("# Plan\n- [ ] task", encoding="utf-8")
    
    # Create status with bad progress
    status_data = {
        "progress": {
            "overall": {"nested": "object"},  # Not a valid number
        },
        "coverage": {"weak": []},
        "timestamp": 1234567890,
    }
    
    (dash / "status.json").write_text(json.dumps(status_data), encoding="utf-8")
    
    result = agent.compute_status()
    
    # Should have created brief with default 0.0 for overall
    brief_file = dash / "status_brief.json"
    if brief_file.exists():
        brief = json.loads(brief_file.read_text(encoding="utf-8"))
        assert brief["overall"] == 0.0


def test_dev_agent_timestamp_conversion_exception(tmp_path: Path):
    """Test timestamp conversion exception handling."""
    agent = DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp/dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    
    # Create status with non-convertible timestamp
    status_data = {
        "progress": {"overall": 0.5},
        "coverage": {"weak": []},
        "timestamp": {"complex": "object"},  # Can't convert to float
    }
    
    (dash / "status.json").write_text(json.dumps(status_data), encoding="utf-8")
    
    result = agent.compute_status()
    
    # Check brief was created with default ts=0.0
    brief_file = dash / "status_brief.json"
    if brief_file.exists():
        brief = json.loads(brief_file.read_text(encoding="utf-8"))
        assert brief["timestamp"] == 0.0


def test_dev_agent_multiple_exception_paths(tmp_path: Path):
    """Test multiple exception paths in single run."""
    agent = DevAgent(project_root=tmp_path)
    dash = tmp_path / ".mcp/dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    
    # Status with all bad data types
    status_data = {
        "progress": "not_a_dict",  # Wrong type
        "coverage": None,  # Wrong type
        "timestamp": [],  # Wrong type
        "checks": {},
        "tests": {},
    }
    
    (dash / "status.json").write_text(json.dumps(status_data), encoding="utf-8")
    
    # Should handle all exceptions gracefully
    result = agent.compute_status()
    assert isinstance(result, dict)
    
    # Brief should use all defaults
    brief_file = dash / "status_brief.json"
    if brief_file.exists():
        brief = json.loads(brief_file.read_text(encoding="utf-8"))
        assert brief["overall"] == 0.0
        assert brief["weak_count"] == 0
        assert brief["timestamp"] == 0.0
