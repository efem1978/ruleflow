"""Test CLI project management commands for coverage."""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import click.exceptions
import pytest

from mcp_rules_assistant.cli import (
    project_add,
    project_current,
    project_list,
    project_remove,
    project_switch,
)


def test_project_list_no_config(tmp_path: Path, monkeypatch, capsys):
    """Test project-list when no config exists."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    
    # Run project-list
    project_list(json_out=False)
    
    captured = capsys.readouterr()
    assert "未找到项目配置" in captured.out


def test_project_switch_not_found_lists_candidates(tmp_path: Path, monkeypatch, capsys):
    """project-switch 名称不存在时应列出候选（覆盖 2062）。"""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    proj_file = fake_home / ".mcp" / "projects.yaml"
    proj_file.parent.mkdir(parents=True, exist_ok=True)
    proj_file.write_text(
        """projects:
  - name: project1
    path: /p1
    active: false
""",
        encoding="utf-8",
    )

    with pytest.raises(click.exceptions.Exit):
        project_switch("not-exist")
    out = capsys.readouterr().out
    assert "项目不存在" in out and "可用项目" in out and "project1" in out


def test_project_list_empty(tmp_path: Path, monkeypatch, capsys):
    """Test project-list with empty projects."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    
    # Create empty projects file
    proj_file = fake_home / ".mcp" / "projects.yaml"
    proj_file.parent.mkdir(parents=True, exist_ok=True)
    proj_file.write_text("projects: []\n", encoding="utf-8")
    
    # Run project-list text mode
    project_list(json_out=False)
    
    captured = capsys.readouterr()
    assert "暂无项目" in captured.out


def test_project_list_with_projects(tmp_path: Path, monkeypatch, capsys):
    """Test project-list with existing projects."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    
    # Create projects file
    proj_file = fake_home / ".mcp" / "projects.yaml"
    proj_file.parent.mkdir(parents=True, exist_ok=True)
    proj_file.write_text(
        """projects:
  - name: project1
    path: /path/to/project1
    active: true
  - name: project2
    path: /path/to/project2
    active: false
""",
        encoding="utf-8",
    )
    
    # Run project-list JSON mode
    project_list(json_out=True)
    
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert len(result["projects"]) == 2
    assert result["projects"][0]["name"] == "project1"
    assert result["projects"][0]["active"] is True


def test_project_list_text_with_projects(tmp_path: Path, monkeypatch, capsys):
    """project-list 文本模式下，存在项目时应打印列表（覆盖 1979-1982）。"""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    proj_file = fake_home / ".mcp" / "projects.yaml"
    proj_file.parent.mkdir(parents=True, exist_ok=True)
    proj_file.write_text(
        """projects:
  - name: project1
    path: /path/to/project1
    active: true
  - name: project2
    path: /path/to/project2
    active: false
""",
        encoding="utf-8",
    )

    project_list(json_out=False)
    out = capsys.readouterr().out
    assert "已记录的项目" in out
    assert "project1" in out and "/path/to/project1" in out


def test_project_list_exception(tmp_path: Path, monkeypatch, capsys):
    """Test project-list with invalid YAML."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    
    # Create invalid YAML
    proj_file = fake_home / ".mcp" / "projects.yaml"
    proj_file.parent.mkdir(parents=True, exist_ok=True)
    proj_file.write_text("invalid: {yaml", encoding="utf-8")
    
    # Should handle exception
    project_list(json_out=False)
    
    captured = capsys.readouterr()
    assert "读取项目配置失败" in captured.out


def test_project_add_success(tmp_path: Path, monkeypatch, capsys):
    """Test project-add successfully adds a project."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    
    # Create a test project directory
    test_proj = tmp_path / "test_project"
    test_proj.mkdir()
    
    # Add project
    project_add(str(test_proj), name="TestProj")
    
    captured = capsys.readouterr()
    assert "项目已添加" in captured.out
    
    # Verify file was created
    proj_file = fake_home / ".mcp" / "projects.yaml"
    assert proj_file.exists()


def test_project_add_path_not_exists(tmp_path: Path, monkeypatch, capsys):
    """Test project-add when path doesn't exist."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    
    # Try to add non-existent path
    with pytest.raises(click.exceptions.Exit):
        project_add("/nonexistent/path")
    
    captured = capsys.readouterr()
    assert "路径不存在" in captured.out


def test_project_add_path_not_dir(tmp_path: Path, monkeypatch, capsys):
    """Test project-add when path is a file."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    
    # Create a file (not directory)
    test_file = tmp_path / "testfile.txt"
    test_file.touch()
    
    # Try to add file as project
    with pytest.raises(click.exceptions.Exit):
        project_add(str(test_file))
    
    captured = capsys.readouterr()
    assert "路径不是目录" in captured.out


def test_project_switch_success(tmp_path: Path, monkeypatch, capsys):
    """Test project-switch successfully switches active project."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    
    # Create projects file
    proj_file = fake_home / ".mcp" / "projects.yaml"
    proj_file.parent.mkdir(parents=True, exist_ok=True)
    proj_file.write_text(
        """projects:
  - name: project1
    path: /path/to/project1
    active: true
  - name: project2
    path: /path/to/project2
    active: false
""",
        encoding="utf-8",
    )
    
    # Switch to project2
    project_switch("project2")
    
    captured = capsys.readouterr()
    assert "已切换到项目" in captured.out


def test_project_switch_no_config(tmp_path: Path, monkeypatch, capsys):
    """Test project-switch when no config exists."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    
    # Try to switch without config
    with pytest.raises(click.exceptions.Exit):
        project_switch("nonexistent")
    
    captured = capsys.readouterr()
    assert "未找到项目配置" in captured.out


def test_project_remove_with_confirm(tmp_path: Path, monkeypatch, capsys):
    """Test project-remove with user confirmation."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    
    # Create projects file
    proj_file = fake_home / ".mcp" / "projects.yaml"
    proj_file.parent.mkdir(parents=True, exist_ok=True)
    proj_file.write_text(
        """projects:
  - name: project1
    path: /path/to/project1
    active: false
""",
        encoding="utf-8",
    )
    
    # Mock typer.confirm to return True
    with mock.patch("typer.confirm", return_value=True):
        project_remove("project1", force=False)
    
    captured = capsys.readouterr()
    assert "项目已移除" in captured.out


def test_project_remove_cancel(tmp_path: Path, monkeypatch, capsys):
    """Test project-remove when user cancels."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    
    # Create projects file
    proj_file = fake_home / ".mcp" / "projects.yaml"
    proj_file.parent.mkdir(parents=True, exist_ok=True)
    proj_file.write_text(
        """projects:
  - name: project1
    path: /path/to/project1
    active: false
""",
        encoding="utf-8",
    )
    
    # Mock typer.confirm to return False (cancel)
    with mock.patch("typer.confirm", return_value=False):
        project_remove("project1", force=False)
    
    captured = capsys.readouterr()
    assert "已取消" in captured.out


def test_project_current_with_active(tmp_path: Path, monkeypatch, capsys):
    """Test project-current when active project exists."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    
    # Create projects file with active project
    proj_file = fake_home / ".mcp" / "projects.yaml"
    proj_file.parent.mkdir(parents=True, exist_ok=True)
    proj_file.write_text(
        """projects:
  - name: project1
    path: /path/to/project1
    active: true
""",
        encoding="utf-8",
    )
    
    # Get current project (JSON)
    project_current(json_out=True)
    
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["current"]["name"] == "project1"


def test_project_current_text_with_active(tmp_path: Path, monkeypatch, capsys):
    """project-current 文本模式下，有活动项目应打印名称与路径（覆盖 2137-2138）。"""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    proj_file = fake_home / ".mcp" / "projects.yaml"
    proj_file.parent.mkdir(parents=True, exist_ok=True)
    proj_file.write_text(
        """projects:
  - name: project1
    path: /path/to/project1
    active: true
""",
        encoding="utf-8",
    )

    project_current(json_out=False)
    out = capsys.readouterr().out
    assert "当前项目" in out and "/path/to/project1" in out


def test_project_current_no_active(tmp_path: Path, monkeypatch, capsys):
    """Test project-current when no active project."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    
    # Create projects file with no active project
    proj_file = fake_home / ".mcp" / "projects.yaml"
    proj_file.parent.mkdir(parents=True, exist_ok=True)
    proj_file.write_text(
        """projects:
  - name: project1
    path: /path/to/project1
    active: false
""",
        encoding="utf-8",
    )
    
    # Get current project (text mode)
    project_current(json_out=False)
    
    captured = capsys.readouterr()
    assert "未设置活动项目" in captured.out


def test_project_current_no_config(tmp_path: Path, monkeypatch, capsys):
    """Test project-current when no config exists."""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    
    # JSON mode
    project_current(json_out=True)
    
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["current"] is None


def test_project_current_text_no_config(tmp_path: Path, monkeypatch, capsys):
    """project-current 文本模式下，无配置时应提示（覆盖 2121）。"""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    project_current(json_out=False)
    out = capsys.readouterr().out
    assert "未找到项目配置" in out


def test_project_remove_no_config(tmp_path: Path, monkeypatch, capsys):
    """project-remove 无配置时应报错并提示（覆盖 2080-2081）。"""
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    with pytest.raises(click.exceptions.Exit):
        project_remove("project1", force=False)
    out = capsys.readouterr().out
    assert "未找到项目配置" in out
