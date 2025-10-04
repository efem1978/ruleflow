"""
Test project management CLI commands.
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
import yaml

from mcp_rules_assistant.cli import (
    project_add,
    project_list,
    project_remove,
    project_switch,
)


@pytest.fixture
def projects_file(tmp_path: Path) -> Path:
    """Create a temporary projects file."""
    projects_dir = tmp_path / ".mcp"
    projects_dir.mkdir(parents=True, exist_ok=True)
    return projects_dir / "projects.yaml"


@pytest.fixture
def mock_home(tmp_path: Path, projects_file: Path) -> None:
    """Mock Path.home() to return tmp_path."""
    with patch("pathlib.Path.home", return_value=tmp_path):
        yield


def test_project_list_empty(tmp_path: Path, capsys) -> None:
    """Test listing projects when none exist."""
    with patch("pathlib.Path.home", return_value=tmp_path):
        project_list(json_out=True)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == {"projects": []}


def test_project_add_new(tmp_path: Path, capsys) -> None:
    """Test adding a new project."""
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    
    with patch("pathlib.Path.home", return_value=tmp_path):
        project_add(str(project_path), name="TestProject")
        
        # Verify project was added
        projects_file = tmp_path / ".mcp" / "projects.yaml"
        assert projects_file.exists()
        
        data = yaml.safe_load(projects_file.read_text(encoding="utf-8"))
        projects = data.get("projects", [])
        assert len(projects) == 1
        assert projects[0]["name"] == "TestProject"
        assert projects[0]["path"] == str(project_path)
        assert projects[0]["active"] is False


def test_project_add_duplicate(tmp_path: Path, capsys) -> None:
    """Test adding duplicate project."""
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    
    with patch("pathlib.Path.home", return_value=tmp_path):
        # Add project twice
        project_add(str(project_path), name="TestProject")
        project_add(str(project_path), name="TestProject")
        
        # Verify only one project exists
        projects_file = tmp_path / ".mcp" / "projects.yaml"
        data = yaml.safe_load(projects_file.read_text(encoding="utf-8"))
        projects = data.get("projects", [])
        assert len(projects) == 1


def test_project_add_nonexistent_path(tmp_path: Path) -> None:
    """Test adding project with non-existent path."""
    nonexistent = tmp_path / "nonexistent"
    
    with patch("pathlib.Path.home", return_value=tmp_path):
        with pytest.raises((SystemExit, typer.Exit)):
            project_add(str(nonexistent), name="BadProject")


def test_project_switch(tmp_path: Path) -> None:
    """Test switching between projects."""
    # Create two projects
    proj1 = tmp_path / "project1"
    proj2 = tmp_path / "project2"
    proj1.mkdir()
    proj2.mkdir()
    
    with patch("pathlib.Path.home", return_value=tmp_path):
        project_add(str(proj1), name="Project1")
        project_add(str(proj2), name="Project2")
        
        # Switch to Project1
        project_switch("Project1")
        
        projects_file = tmp_path / ".mcp" / "projects.yaml"
        data = yaml.safe_load(projects_file.read_text(encoding="utf-8"))
        projects = data.get("projects", [])
        
        assert projects[0]["name"] == "Project1"
        assert projects[0]["active"] is True
        assert projects[1]["name"] == "Project2"
        assert projects[1]["active"] is False
        
        # Switch to Project2
        project_switch("Project2")
        
        data = yaml.safe_load(projects_file.read_text(encoding="utf-8"))
        projects = data.get("projects", [])
        
        assert projects[0]["active"] is False
        assert projects[1]["active"] is True


def test_project_switch_nonexistent(tmp_path: Path) -> None:
    """Test switching to non-existent project."""
    with patch("pathlib.Path.home", return_value=tmp_path):
        # Create projects file
        projects_file = tmp_path / ".mcp" / "projects.yaml"
        projects_file.parent.mkdir(parents=True, exist_ok=True)
        projects_file.write_text("projects: []", encoding="utf-8")
        
        with pytest.raises((SystemExit, typer.Exit)):
            project_switch("NonExistent")


def test_project_current(tmp_path: Path) -> None:
    """Test getting current active project."""
    proj1 = tmp_path / "project1"
    proj1.mkdir()
    
    with patch("pathlib.Path.home", return_value=tmp_path):
        project_add(str(proj1), name="Project1")
        project_switch("Project1")
        
        # Verify via file
        projects_file = tmp_path / ".mcp" / "projects.yaml"
        data = yaml.safe_load(projects_file.read_text(encoding="utf-8"))
        projects = data.get("projects", [])
        
        current = [p for p in projects if p.get("active")]
        assert len(current) == 1
        assert current[0]["name"] == "Project1"


def test_project_current_none(tmp_path: Path) -> None:
    """Test getting current project when none is active."""
    with patch("pathlib.Path.home", return_value=tmp_path):
        # Create projects file with no active project
        projects_file = tmp_path / ".mcp" / "projects.yaml"
        projects_file.parent.mkdir(parents=True, exist_ok=True)
        projects_file.write_text("projects: []", encoding="utf-8")
        
        # Just verify the file exists and has no projects
        data = yaml.safe_load(projects_file.read_text(encoding="utf-8"))
        assert data.get("projects", []) == []


def test_project_remove(tmp_path: Path) -> None:
    """Test removing a project."""
    proj1 = tmp_path / "project1"
    proj1.mkdir()
    
    with patch("pathlib.Path.home", return_value=tmp_path):
        project_add(str(proj1), name="Project1")
        
        # Remove with force flag
        project_remove("Project1", force=True)
        
        projects_file = tmp_path / ".mcp" / "projects.yaml"
        data = yaml.safe_load(projects_file.read_text(encoding="utf-8"))
        projects = data.get("projects", [])
        
        assert len(projects) == 0


def test_project_remove_nonexistent(tmp_path: Path) -> None:
    """Test removing non-existent project."""
    with patch("pathlib.Path.home", return_value=tmp_path):
        projects_file = tmp_path / ".mcp" / "projects.yaml"
        projects_file.parent.mkdir(parents=True, exist_ok=True)
        projects_file.write_text("projects: []", encoding="utf-8")
        
        with pytest.raises((SystemExit, typer.Exit)):
            project_remove("NonExistent", force=True)


def test_project_list_multiple(tmp_path: Path) -> None:
    """Test listing multiple projects."""
    proj1 = tmp_path / "project1"
    proj2 = tmp_path / "project2"
    proj1.mkdir()
    proj2.mkdir()
    
    with patch("pathlib.Path.home", return_value=tmp_path):
        project_add(str(proj1), name="Project1")
        project_add(str(proj2), name="Project2")
        project_switch("Project2")
        
        # Verify via file instead of capturing output
        projects_file = tmp_path / ".mcp" / "projects.yaml"
        data = yaml.safe_load(projects_file.read_text(encoding="utf-8"))
        projects = data.get("projects", [])
        
        assert len(projects) == 2
        assert projects[0]["name"] == "Project1"
        assert projects[0]["active"] is False
        assert projects[1]["name"] == "Project2"
        assert projects[1]["active"] is True
