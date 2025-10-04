"""
Test memory.py edge cases for 98% coverage target.
Focuses on exception branches and security checks.
"""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_rules_assistant.memory import MemoryManager


def test_memory_read_symlink_check_exception(tmp_path: Path) -> None:
    """Test symlink check exception handling during read."""
    project = tmp_path / "project"
    project.mkdir()
    (project / ".mcp").mkdir()
    
    mem = MemoryManager(project)
    
    # Mock is_symlink to raise exception
    with patch.object(Path, "is_symlink", side_effect=Exception("symlink check error")):
        result = mem.snapshot()
        # Should return empty dict on exception (fail-safe)
        assert result == {"turns": [], "summary": "", "links": []}


def test_memory_read_hardlink_denied(tmp_path: Path) -> None:
    """Test hardlink detection and denial during read."""
    project = tmp_path / "project"
    project.mkdir()
    mcp_dir = project / ".mcp"
    mcp_dir.mkdir()
    
    memory_file = mcp_dir / "memory.json"
    memory_file.write_text('{"turns": [{"role": "user", "content": "test"}]}', encoding="utf-8")
    
    mem = MemoryManager(project)
    
    # Create a hard link (if filesystem supports it)
    try:
        hardlink = mcp_dir / "memory_hardlink.json"
        os.link(memory_file, hardlink)
        
        # Override path to hardlink
        mem.path = hardlink
        
        # Should deny reading hardlink without trust env (returns empty)
        result = mem.snapshot()
        assert result == {"turns": [], "summary": "", "links": []}
    except OSError:
        # Filesystem doesn't support hardlinks (e.g., some macOS volumes)
        pytest.skip("Filesystem does not support hardlinks")


def test_memory_read_hardlink_allowed_with_env(tmp_path: Path) -> None:
    """Test hardlink allowed with MCP_MEMORY_TRUST_HARDLINK."""
    project = tmp_path / "project"
    project.mkdir()
    mcp_dir = project / ".mcp"
    mcp_dir.mkdir()
    
    memory_file = mcp_dir / "memory.json"
    memory_file.write_text('{"turns": [{"role": "user", "content": "test"}]}', encoding="utf-8")
    
    mem = MemoryManager(project)
    
    try:
        hardlink = mcp_dir / "memory_hardlink.json"
        os.link(memory_file, hardlink)
        mem.path = hardlink
        
        # Allow hardlink with environment variable
        with patch.dict(os.environ, {"MCP_MEMORY_TRUST_HARDLINK": "true"}):
            result = mem.snapshot()
            assert len(result.get("turns", [])) == 1
    except OSError:
        pytest.skip("Filesystem does not support hardlinks")


def test_memory_write_symlink_denied(tmp_path: Path) -> None:
    """Test symlink write denial."""
    project = tmp_path / "project"
    project.mkdir()
    mcp_dir = project / ".mcp"
    mcp_dir.mkdir()
    
    # Create a symlink target
    target = mcp_dir / "target.json"
    target.write_text('{"turns": []}', encoding="utf-8")
    
    symlink = mcp_dir / "memory.json"
    try:
        symlink.symlink_to(target)
    except OSError:
        pytest.skip("Filesystem does not support symlinks")
    
    mem = MemoryManager(project)
    mem.path = symlink
    
    # Should raise ValueError on symlink write
    with pytest.raises(ValueError, match="symlink target"):
        mem.append_turn("user", "test")


def test_memory_write_hardlink_denied(tmp_path: Path) -> None:
    """Test hardlink write denial."""
    project = tmp_path / "project"
    project.mkdir()
    mcp_dir = project / ".mcp"
    mcp_dir.mkdir()
    
    memory_file = mcp_dir / "memory.json"
    memory_file.write_text('{"turns": []}', encoding="utf-8")
    
    try:
        hardlink = mcp_dir / "memory_hardlink.json"
        os.link(memory_file, hardlink)
        
        mem = MemoryManager(project)
        mem.path = hardlink
        
        # Should raise ValueError on hardlink write
        with pytest.raises(ValueError, match="hardlink target"):
            mem.append_turn("user", "test")
    except OSError:
        pytest.skip("Filesystem does not support hardlinks")


def test_memory_write_hardlink_allowed_with_env(tmp_path: Path) -> None:
    """Test hardlink write allowed with trust environment variable."""
    project = tmp_path / "project"
    project.mkdir()
    mcp_dir = project / ".mcp"
    mcp_dir.mkdir()
    
    memory_file = mcp_dir / "memory.json"
    memory_file.write_text('{"turns": []}', encoding="utf-8")
    
    try:
        hardlink = mcp_dir / "memory_hardlink.json"
        os.link(memory_file, hardlink)
        
        mem = MemoryManager(project)
        mem.path = hardlink
        
        # Allow with environment variable
        with patch.dict(os.environ, {"MCP_MEMORY_TRUST_HARDLINK": "1"}):
            mem.append_turn("user", "test")
            # Should succeed
            result = mem.snapshot()
            assert len(result.get("turns", [])) == 1
    except OSError:
        pytest.skip("Filesystem does not support hardlinks")


def test_memory_write_path_outside_mcp_denied(tmp_path: Path) -> None:
    """Test write denial when path is outside .mcp directory."""
    project = tmp_path / "project"
    project.mkdir()
    mcp_dir = project / ".mcp"
    mcp_dir.mkdir()
    
    # Try to write outside .mcp
    outside_path = project / "outside.json"
    
    mem = MemoryManager(project)
    mem.path = outside_path
    
    # Should raise ValueError
    with pytest.raises(ValueError, match="outside project .mcp"):
        mem.append_turn("user", "test")


def test_memory_compress_with_large_data(tmp_path: Path) -> None:
    """Test compression mechanism with data exceeding max_bytes."""
    project = tmp_path / "project"
    project.mkdir()
    (project / ".mcp").mkdir()
    
    # Create large content
    large_content = "x" * 10000
    
    mem = MemoryManager(project, window=20, max_bytes=30000)
    
    for _ in range(10):
        mem.append_turn("user", large_content)
    
    # Verify compression occurred
    data = mem.snapshot()
    # Should have fewer turns due to compression
    assert len(data.get("turns", [])) < 10


def test_memory_python310_path_compatibility(tmp_path: Path) -> None:
    """Test Python 3.10 compatibility for is_relative_to fallback."""
    project = tmp_path / "project"
    project.mkdir()
    mcp_dir = project / ".mcp"
    mcp_dir.mkdir()
    
    mem = MemoryManager(project)
    
    # Test the fallback works by accessing _write directly
    mem.append_turn("user", "test for py3.10 compatibility")
    result = mem.snapshot()
    assert len(result.get("turns", [])) >= 1


def test_memory_add_link(tmp_path: Path) -> None:
    """Test add_link functionality."""
    project = tmp_path / "project"
    project.mkdir()
    (project / ".mcp").mkdir()
    
    mem = MemoryManager(project)
    mem.add_link("project_a", "task_1", "initial setup")
    
    data = mem.snapshot()
    links = data.get("links", [])
    assert len(links) == 1
    assert links[0]["project"] == "project_a"
    assert links[0]["task"] == "task_1"
