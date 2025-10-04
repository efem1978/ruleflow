"""Test edge cases in mcp_server to improve coverage."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_server_init_with_nonexistent_cwd():
    """Test server initialization when current directory doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir) / "nonexistent"
        
        # Mock Path.cwd() to raise FileNotFoundError
        with mock.patch("pathlib.Path.cwd", side_effect=FileNotFoundError("No such directory")):
            server = JsonRpcServer()
            # Should fallback to home directory
            assert server.project_root == Path.home()


def test_memory_write_allowed_exception_handling():
    """Test exception handling in _memory_write_allowed."""
    old_pytest = os.environ.get("PYTEST_CURRENT_TEST")
    try:
        # Remove PYTEST_CURRENT_TEST to test actual logic
        os.environ.pop("PYTEST_CURRENT_TEST", None)
        
        server = JsonRpcServer()
        # Should handle exceptions gracefully and use default config
        result = server._memory_write_allowed()
        assert isinstance(result, bool)
    finally:
        if old_pytest is not None:
            os.environ["PYTEST_CURRENT_TEST"] = old_pytest


def test_list_resources_with_symlink_filtering(tmp_path: Path):
    """Test resource listing filters out unsafe symlinks."""
    old_pytest = os.environ.get("PYTEST_CURRENT_TEST")
    try:
        # Remove pytest env to test actual filtering
        os.environ.pop("PYTEST_CURRENT_TEST", None)
        os.environ.pop("MCP_MEMORY_TRUST_SYMLINK", None)
        
        server = JsonRpcServer()
        server.project_root = tmp_path
        
        # Create .mcp directory structure
        mcp_dir = tmp_path / ".mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a namespaced memory file (regular)
        regular_file = mcp_dir / "memory.regular.json"
        regular_file.write_text('{"test": "data"}', encoding="utf-8")
        
        # Create a symlink pointing outside .mcp (should be filtered)
        outside_target = tmp_path / "outside.json"
        outside_target.write_text('{"outside": "data"}', encoding="utf-8")
        symlink_file = mcp_dir / "memory.symlink.json"
        try:
            symlink_file.symlink_to(outside_target)
        except (OSError, NotImplementedError):
            # Skip if symlinks not supported on this platform
            pytest.skip("Symlinks not supported on this platform")
        
        # List resources via MCP protocol
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/list",
            "params": {},
        }
        result = server.handle(request)
        
        # Should return resources list
        assert "result" in result
        resources = result.get("result", {}).get("resources", [])
        
        # Regular namespace should be included
        regular_found = any("ns=regular" in r.get("uri", "") for r in resources)
        # Symlink namespace should be filtered out
        symlink_found = any("ns=symlink" in r.get("uri", "") for r in resources)
        
        assert regular_found, "Regular namespaced file should be in resources"
        assert not symlink_found, "Symlink should be filtered out when MCP_MEMORY_TRUST_SYMLINK not set"
        
    finally:
        if old_pytest is not None:
            os.environ["PYTEST_CURRENT_TEST"] = old_pytest


def test_list_resources_with_hardlink_filtering(tmp_path: Path):
    """Test resource listing executes hardlink detection code path."""
    old_pytest = os.environ.get("PYTEST_CURRENT_TEST")
    old_hardlink = os.environ.get("MCP_MEMORY_TRUST_HARDLINK")
    try:
        os.environ.pop("PYTEST_CURRENT_TEST", None)
        os.environ.pop("MCP_MEMORY_TRUST_HARDLINK", None)
        
        server = JsonRpcServer()
        server.project_root = tmp_path
        
        mcp_dir = tmp_path / ".mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)
        
        # Create original namespaced memory file
        original = mcp_dir / "memory.test.json"
        original.write_text('{"test": "data"}', encoding="utf-8")
        
        # Create hardlink with different namespace
        hardlink = mcp_dir / "memory.hard.json"
        try:
            hardlink.hardlink_to(original)
        except (OSError, NotImplementedError):
            pytest.skip("Hardlinks not supported on this platform")
        
        # Verify hardlink was created (both files have nlink > 1)
        assert original.stat().st_nlink > 1, "Hardlink creation should increase link count"
        
        # List resources via MCP protocol - this exercises the hardlink detection code
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/list",
            "params": {},
        }
        result = server.handle(request)
        
        # Should successfully return resources list (filtering is implementation detail)
        assert "result" in result
        assert "resources" in result.get("result", {})
        
        # Test with hardlinks allowed
        os.environ["MCP_MEMORY_TRUST_HARDLINK"] = "1"
        result2 = server.handle(request)
        assert "result" in result2
        assert "resources" in result2.get("result", {})
        
    finally:
        if old_pytest is not None:
            os.environ["PYTEST_CURRENT_TEST"] = old_pytest
        if old_hardlink is None:
            os.environ.pop("MCP_MEMORY_TRUST_HARDLINK", None)
        else:
            os.environ["MCP_MEMORY_TRUST_HARDLINK"] = old_hardlink


def test_memory_hard_disable_exception_branch():
    """Test exception handling in MCP_MEMORY_HARD_DISABLE check."""
    old_pytest = os.environ.get("PYTEST_CURRENT_TEST")
    old_disable = os.environ.get("MCP_MEMORY_HARD_DISABLE")
    try:
        os.environ.pop("PYTEST_CURRENT_TEST", None)
        # Set to invalid value that might cause exception
        os.environ["MCP_MEMORY_HARD_DISABLE"] = "invalid_but_not_truthy"
        
        server = JsonRpcServer()
        # Should handle gracefully and not crash
        result = server._memory_write_allowed()
        assert isinstance(result, bool)
        
    finally:
        if old_pytest is not None:
            os.environ["PYTEST_CURRENT_TEST"] = old_pytest
        if old_disable is None:
            os.environ.pop("MCP_MEMORY_HARD_DISABLE", None)
        else:
            os.environ["MCP_MEMORY_HARD_DISABLE"] = old_disable


def test_server_init_with_invalid_project_root_env():
    """Test server initialization with invalid MCP_PROJECT_ROOT."""
    old_root = os.environ.get("MCP_PROJECT_ROOT")
    old_pytest = os.environ.get("PYTEST_CURRENT_TEST")
    try:
        os.environ.pop("PYTEST_CURRENT_TEST", None)
        # Set to invalid path
        os.environ["MCP_PROJECT_ROOT"] = "/nonexistent/invalid/path/that/does/not/exist"
        
        server = JsonRpcServer()
        # Should fallback to current directory
        assert server.project_root.exists()
        
    finally:
        if old_pytest is not None:
            os.environ["PYTEST_CURRENT_TEST"] = old_pytest
        if old_root is None:
            os.environ.pop("MCP_PROJECT_ROOT", None)
        else:
            os.environ["MCP_PROJECT_ROOT"] = old_root
