import json
import shutil
from pathlib import Path

import pytest

from mcp_rules_assistant.dev_agent import DevAgent


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Create a temporary project root with mock files."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".mcp").mkdir()
    (project_root / "docs").mkdir()

    # Create mock plan.md
    (project_root / ".mcp" / "plan.md").write_text(
        """
# Plan
- Status: planned

## Next Actions
- [ ] Task 1
- [x] Task 2
"""
    )

    # Create mock dashboard status
    dashboard_dir = project_root / ".mcp" / "dashboard"
    dashboard_dir.mkdir()
    (dashboard_dir / "status.json").write_text(
        json.dumps(
            {
                "coverage": {
                    "weak": ["module1", "module2"],
                    "groups": [],
                    "near": [],
                    "min_module": 0.9,
                    "count": 10,
                    "progress": 0.8,
                }
            }
        )
    )

    # Create dummy files for coverage summary
    (project_root / "mcp_rules_assistant").mkdir(exist_ok=True)
    (project_root / "coverage.xml").write_text(
        """<?xml version="1.0" ?>
<coverage lines-valid="0" lines-covered="0" line-rate="1" branches-valid="0" branches-covered="0" branch-rate="1" timestamp="1625893200" complexity="0" version="6.0">
    <sources>
        <source>.</source>
    </sources>
    <packages>
        <package name="mcp_rules_assistant" line-rate="1" branch-rate="1" complexity="0">
            <classes>
            </classes>
        </package>
    </packages>
</coverage>"""
    )

    # Copy real config to temp project
    (project_root / ".mcp/assistant.yaml").touch()
    shutil.copyfile(".mcp/assistant.yaml", project_root / ".mcp/assistant.yaml")

    return project_root


def test_dev_agent_initialization(project_root: Path):
    """
    Test that the DevAgent can be initialized.
    """
    agent = DevAgent(project_root=project_root)
    assert agent is not None
    assert agent.project_root == project_root


def test_compute_status(project_root: Path, monkeypatch):
    """
    Test the compute_status method.
    """
    # Mock the summarize functions to avoid dependency on real coverage data
    monkeypatch.setattr(
        "mcp_rules_assistant.dev_agent.summarize",
        lambda **kwargs: {"weak": [], "count": 10},
    )
    monkeypatch.setattr(
        "mcp_rules_assistant.dev_agent.summarize_groups",
        lambda **kwargs: {"groups": []},
    )
    monkeypatch.setattr(
        "mcp_rules_assistant.dev_agent.summarize_near", lambda **kwargs: {"near": []}
    )

    agent = DevAgent(project_root=project_root)
    status = agent.compute_status()

    assert isinstance(status, dict)
    assert "plan" in status
    assert "coverage" in status
    assert "progress" in status
    assert "tasks" in status

    assert status["plan"]["status"] == "in_progress"
    assert status["plan"]["current"] == "Task 1"

    assert len(status["coverage"]["weak"]) == 0
    assert status["progress"]["plan"] == 0.5
    assert status["tasks"]["pending"] == ["Task 1"]
    assert status["tasks"]["done"] == ["Task 2"]


def test_atomic_write_failure(project_root: Path, monkeypatch):
    """
    Test that file writes are atomic and don't corrupt files on failure.
    """
    agent = DevAgent(project_root=project_root)
    status_path = project_root / ".mcp" / "dashboard" / "status.json"

    # Prevent the agent from clearing the directory during this specific test
    # by replacing the method with a no-op version that just ensures the dir exists.
    def mock_ensure_dashboard_dir(rebuild=False):
        status_path.parent.mkdir(parents=True, exist_ok=True)
        return status_path.parent

    monkeypatch.setattr(agent, "_ensure_dashboard_dir", mock_ensure_dashboard_dir)

    # Create an initial status file
    original_content = '{"initial": "content"}'
    status_path.write_text(original_content, encoding="utf-8")

    # Mock shutil.move to raise an exception to simulate a failed atomic move
    def mock_move(*args, **kwargs):
        # In a real failure, the source (temp file) would still exist.
        # The _atomic_write function is expected to clean it up.
        raise IOError("Permission denied during move")

    monkeypatch.setattr(shutil, "move", mock_move)

    # The run method should catch the exception from _atomic_write and not corrupt the file
    agent.run(interval=1, max_cycles=1)

    # Check that the original file is untouched
    assert status_path.read_text() == original_content

    # Check that the temp file was cleaned up by the exception handler in _atomic_write
    temp_files = list(status_path.parent.glob("*.tmp*"))
    assert not temp_files, f"Temporary files not cleaned up: {temp_files}"
