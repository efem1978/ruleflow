"""Test mcp_server.py exception handling branches for coverage."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock


from mcp_rules_assistant.mcp_server import JsonRpcServer


# Note: _append_status_info is actually named _dashboard_append_info in mcp_server.py


def test_memory_hard_disable_exception(tmp_path: Path, monkeypatch):
    """Test _memory_write_allowed with MCP_MEMORY_HARD_DISABLE exception (line 101)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))
    
    # Mock os.environ.get to raise exception for HARD_DISABLE
    original_get = os.environ.get
    
    def mock_get(key, default=None):
        if key == "PYTEST_CURRENT_TEST":
            return None  # Not in pytest
        if key == "MCP_MEMORY_HARD_DISABLE":
            raise RuntimeError("Simulated exception")
        return original_get(key, default)
    
    monkeypatch.setattr(os.environ, "get", mock_get)
    
    srv = JsonRpcServer()
    # Should handle exception and continue (not crash)
    result = srv._memory_write_allowed()
    assert isinstance(result, bool)


def test_strict_isolation_exception(tmp_path: Path, monkeypatch):
    """Test _memory_write_allowed with MCP_STRICT_ISOLATION exception (line 121)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))
    
    # Mock os.environ.get to raise exception for STRICT_ISOLATION
    original_get = os.environ.get
    
    def mock_get(key, default=None):
        if key == "PYTEST_CURRENT_TEST":
            return None
        if key == "MCP_MEMORY_HARD_DISABLE":
            return "0"
        if key == "MCP_STRICT_ISOLATION":
            raise RuntimeError("Simulated exception")
        return original_get(key, default)
    
    monkeypatch.setattr(os.environ, "get", mock_get)
    
    srv = JsonRpcServer()
    # Should handle exception and continue
    result = srv._memory_write_allowed()
    assert isinstance(result, bool)


def test_append_status_info_invalid_json(tmp_path: Path, monkeypatch):
    """Test _dashboard_append_info with invalid JSON (line 225-226)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))
    
    # Create dashboard with invalid JSON
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    status_file = dash / "status.json"
    status_file.write_text("invalid {json", encoding="utf-8")
    
    srv = JsonRpcServer()
    # Should handle exception gracefully
    srv._dashboard_append_info("test message")
    
    # Should have created valid JSON
    assert status_file.exists()
    data = json.loads(status_file.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_append_status_info_generate_exception(tmp_path: Path, monkeypatch):
    """Test _dashboard_append_info when generate_status fails (line 232-233)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))
    
    # Create .mcp but no status.json
    mcp_dir = tmp_path / ".mcp"
    mcp_dir.mkdir()
    dash = mcp_dir / "dashboard"
    dash.mkdir()
    
    # Mock generate_status to raise exception
    with mock.patch("mcp_rules_assistant.auto_status.generate_status", side_effect=RuntimeError("Mock error")):
        srv = JsonRpcServer()
        # Should handle exception and use empty dict
        srv._dashboard_append_info("test message")
    
    # Should have created file with minimal data
    status_file = dash / "status.json"
    assert status_file.exists()


def test_resources_list_is_relative_to_exception(tmp_path: Path, monkeypatch):
    """Test resources/list with is_relative_to exception (line 428-431)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))
    
    # Create .mcp directory
    mcp_dir = tmp_path / ".mcp"
    mcp_dir.mkdir()
    
    # Create a memory file
    memory_file = mcp_dir / "memory.test.json"
    memory_file.write_text('[]', encoding="utf-8")
    
    # Mock is_relative_to to raise exception
    original_is_relative_to = Path.is_relative_to
    
    def mock_is_relative_to(self, *args):
        raise AttributeError("is_relative_to not available")
    
    monkeypatch.setattr(Path, "is_relative_to", mock_is_relative_to)
    
    srv = JsonRpcServer()
    
    # List resources - should handle exception and use fallback logic
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "resources/list",
        "params": {}
    }
    result = srv.handle(request)
    
    # Should succeed with fallback logic
    assert "result" in result
    assert "resources" in result["result"]


def test_resources_list_nlink_exception(tmp_path: Path, monkeypatch):
    """Test resources/list with st_nlink exception (line 444-445)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))
    
    # Create .mcp directory
    mcp_dir = tmp_path / ".mcp"
    mcp_dir.mkdir()
    
    # Create a memory file
    memory_file = mcp_dir / "memory.test.json"
    memory_file.write_text('[]', encoding="utf-8")
    
    # Mock Path.stat to raise exception for st_nlink
    original_stat = Path.stat
    
    def mock_stat(self, follow_symlinks=True):
        stat_result = original_stat(self, follow_symlinks=follow_symlinks)
        # Create a mock stat_result that raises on st_nlink access
        class MockStat:
            @property
            def st_nlink(self):
                raise OSError("Cannot get nlink")
        return MockStat()
    
    monkeypatch.setattr(Path, "stat", mock_stat)
    
    srv = JsonRpcServer()
    
    # List resources - should handle exception and default to nlink=1
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "resources/list",
        "params": {}
    }
    result = srv.handle(request)
    
    # Should succeed with default nlink
    assert "result" in result
    assert "resources" in result["result"]


def test_resources_list_overall_exception(tmp_path: Path, monkeypatch):
    """Test resources/list with overall exception (line 448-449)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))
    
    # Create .mcp directory
    mcp_dir = tmp_path / ".mcp"
    mcp_dir.mkdir()
    
    # Create a memory file
    memory_file = mcp_dir / "memory.test.json"
    memory_file.write_text('[]', encoding="utf-8")
    
    # Mock resolve() to raise exception
    original_resolve = Path.resolve
    
    def mock_resolve(self):
        if "memory" in str(self):
            raise RuntimeError("Simulated resolve error")
        return original_resolve(self)
    
    monkeypatch.setattr(Path, "resolve", mock_resolve)
    
    srv = JsonRpcServer()
    
    # List resources - should handle exception and skip problematic file
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "resources/list",
        "params": {}
    }
    result = srv.handle(request)
    
    # Should succeed (file skipped due to exception)
    assert "result" in result
    assert "resources" in result["result"]


def test_append_status_info_non_dict_data(tmp_path: Path, monkeypatch):
    """Test _dashboard_append_info when data is not a dict (line 224)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))
    
    # Create dashboard with non-dict JSON
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    status_file = dash / "status.json"
    status_file.write_text('["not", "a", "dict"]', encoding="utf-8")
    
    srv = JsonRpcServer()
    # Should handle non-dict and convert to dict
    srv._dashboard_append_info("test message")
    
    # Should have overwritten with dict
    data = json.loads(status_file.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_append_status_info_string_in_info_list(tmp_path: Path, monkeypatch):
    """Test _dashboard_append_info with string in info list (line 243-244)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))
    
    # Create dashboard with info as list of strings
    dash = tmp_path / ".mcp" / "dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    status_file = dash / "status.json"
    status_file.write_text('{"info": ["string1", "string2"]}', encoding="utf-8")
    
    srv = JsonRpcServer()
    # Should normalize strings to objects
    srv._dashboard_append_info("new message")
    
    data = json.loads(status_file.read_text(encoding="utf-8"))
    # All info items should be dicts with "text" key
    for item in data.get("info", []):
        assert isinstance(item, dict)
        assert "text" in item
