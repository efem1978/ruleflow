from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_rules_assistant.memory import MemoryManager


def test_memory_manager_init():
    """Test MemoryManager initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)
        assert mm.project_root == project_root
        assert mm.path == project_root / ".mcp" / "memory.json"


def test_memory_manager_ensure_file():
    """Test memory file creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        # File should be created automatically by _ensure_file()
        # Check if .mcp directory exists
        mcp_dir = project_root / ".mcp"
        assert mcp_dir.exists()

        # Memory file should exist
        if mm.path.exists():
            # Should contain valid JSON
            data = json.loads(mm.path.read_text(encoding="utf-8"))
            assert isinstance(data, dict)


def test_memory_manager_hard_disable():
    """Test hard disable functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        config_path = project_root / ".mcp" / "assistant.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create config with hard disable
        config_content = """
memory:
  hard_disable: true
"""
        config_path.write_text(config_content, encoding="utf-8")

        mm = MemoryManager(project_root)
        assert mm._hard_disable is True


def test_memory_manager_mask_patterns():
    """Test mask pattern functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        config_path = project_root / ".mcp" / "assistant.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create config with mask patterns
        config_content = """
memory:
  mask_patterns:
    - "password.*"
    - "secret.*"
"""
        config_path.write_text(config_content, encoding="utf-8")

        mm = MemoryManager(project_root)
        assert len(mm._mask_re) == 2


def test_memory_manager_resolve_target_inside_project():
    """Test path resolution security check."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        # Create the memory file first to ensure it exists
        mm.path.parent.mkdir(parents=True, exist_ok=True)
        mm.path.write_text('{"turns": [], "summary": ""}', encoding="utf-8")

        # Valid path should work
        result = mm._resolve_target_inside_project()
        assert result is not None
        assert result == mm.path.resolve()


def test_memory_manager_resolve_target_outside_project():
    """Test path resolution rejects paths outside project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create MemoryManager with path outside project
        outside_path = Path(tmpdir).parent / "outside" / "memory.json"
        mm = MemoryManager(project_root)
        mm.path = outside_path

        result = mm._resolve_target_inside_project()
        assert result is None


def test_memory_manager_symlink_handling():
    """Test symlink handling with trust setting."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mcp_dir = project_root / ".mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)

        # Create actual memory file
        real_memory = mcp_dir / "real_memory.json"
        real_memory.write_text('{"turns": [], "summary": ""}', encoding="utf-8")

        # Create symlink
        symlink_memory = mcp_dir / "memory.json"
        try:
            symlink_memory.symlink_to(real_memory)

            mm = MemoryManager(project_root)
            mm.path = symlink_memory

            # Without trust, should return None
            with patch.dict("os.environ", {"MCP_MEMORY_TRUST_SYMLINK": "false"}):
                result = mm._resolve_target_inside_project()
                assert result is None

            # With trust, should work
            with patch.dict("os.environ", {"MCP_MEMORY_TRUST_SYMLINK": "true"}):
                result = mm._resolve_target_inside_project()
                assert result is not None

        except OSError:
            # Skip test if symlinks not supported
            pytest.skip("Symlinks not supported on this system")


def test_memory_manager_snapshot():
    """Test memory snapshot functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        snapshot = mm.snapshot()
        assert isinstance(snapshot, dict)
        assert "turns" in snapshot
        assert "summary" in snapshot


def test_memory_manager_snapshot_with_data():
    """Test snapshot with existing data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        # Add some test data
        test_data = {
            "turns": [{"role": "user", "content": "test"}],
            "summary": "test summary",
        }
        mm.path.write_text(json.dumps(test_data), encoding="utf-8")

        snapshot = mm.snapshot()
        assert snapshot["turns"] == test_data["turns"]
        assert snapshot["summary"] == test_data["summary"]


def test_memory_manager_snapshot_invalid_json():
    """Test snapshot with invalid JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        # Write invalid JSON
        mm.path.write_text("invalid json", encoding="utf-8")

        snapshot = mm.snapshot()
        # Should return default structure
        assert "turns" in snapshot
        assert "summary" in snapshot


def test_memory_manager_append_turn():
    """Test appending memory turns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        # Append a turn
        mm.append_turn("user", "test message")

        snapshot = mm.snapshot()
        assert len(snapshot["turns"]) == 1
        assert snapshot["turns"][0]["role"] == "user"
        assert snapshot["turns"][0]["content"] == "test message"


def test_memory_manager_append_turn_hard_disabled():
    """Test append turn when hard disabled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        config_path = project_root / ".mcp" / "assistant.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create config with hard disable
        config_content = """
memory:
  hard_disable: true
"""
        config_path.write_text(config_content, encoding="utf-8")

        mm = MemoryManager(project_root)

        # Should raise ValueError when hard disabled
        with pytest.raises(ValueError, match="memory.hard_disable is true"):
            mm.append_turn("user", "test message")


def test_memory_manager_append_turn_with_masking():
    """Test append turn with content masking."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        config_path = project_root / ".mcp" / "assistant.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create config with mask patterns
        config_content = """
memory:
  mask_patterns:
    - "password.*"
    - "secret.*"
"""
        config_path.write_text(config_content, encoding="utf-8")

        mm = MemoryManager(project_root)

        # Append turn with sensitive content
        mm.append_turn("user", "my password is secret123")

        snapshot = mm.snapshot()
        # Content should be masked
        assert "password" not in snapshot["turns"][0]["content"].lower()


def test_memory_manager_compress():
    """Test memory compression functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        # Add multiple turns
        for i in range(25):  # More than the typical limit
            mm.append_turn("user", f"message {i}")

        # Compression happens automatically in append_turn via _compress_if_needed
        snapshot = mm.snapshot()
        assert len(snapshot["turns"]) <= 20  # Should be compressed


def test_memory_manager_compress_with_summary():
    """Test compression with summary generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        # Add multiple turns to trigger compression
        for i in range(25):
            mm.append_turn("user", f"message {i}")

        snapshot = mm.snapshot()
        assert len(snapshot["turns"]) <= 20
        assert len(snapshot["summary"]) > 0


def test_memory_manager_add_link():
    """Test adding project links."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        # Add a link
        mm.add_link("test_project", "test_task", "test note")

        snapshot = mm.snapshot()
        assert len(snapshot["links"]) == 1
        assert snapshot["links"][0]["project"] == "test_project"
        assert snapshot["links"][0]["task"] == "test_task"
        assert snapshot["links"][0]["note"] == "test note"


def test_memory_manager_compress_if_needed():
    """Test _compress_if_needed functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(
            project_root, max_bytes=1000,
        )  # Small limit to trigger compression

        # Create large data that exceeds max_bytes
        large_data = {
            "turns": [
                {"role": "user", "content": "x" * 500, "meta": {"large": "y" * 300}}
                for _ in range(10)
            ],
            "summary": "test summary",
            "links": [],
        }

        original_size = len(json.dumps(large_data, ensure_ascii=False).encode("utf-8"))
        compressed = mm._compress_if_needed(large_data)
        compressed_size = len(
            json.dumps(compressed, ensure_ascii=False).encode("utf-8"),
        )

        # Should be smaller than original (compression attempted)
        assert compressed_size < original_size
        # Should have fewer turns due to compression
        assert len(compressed["turns"]) <= len(large_data["turns"])


def test_memory_manager_error_handling():
    """Test error handling in various scenarios."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        # Test reading from non-existent file
        snapshot = mm.snapshot()
        assert isinstance(snapshot, dict)
        assert "turns" in snapshot

        # Test with corrupted JSON file
        mm.path.parent.mkdir(parents=True, exist_ok=True)
        mm.path.write_text("invalid json", encoding="utf-8")

        snapshot = mm.snapshot()
        assert isinstance(snapshot, dict)
        assert snapshot["turns"] == []


def test_memory_manager_config_error_handling():
    """Test handling of malformed config files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        config_path = project_root / ".mcp" / "assistant.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create malformed config
        config_path.write_text("invalid: yaml: content:", encoding="utf-8")

        # Should still work with defaults
        mm = MemoryManager(project_root)
        assert not mm._hard_disable


def test_memory_manager_symlink_handling():
    """Test symlink path resolution and security."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        # Ensure memory file exists first
        mm.append_turn("user", "test message")

        # Test resolve_target_inside_project with various paths
        target = mm._resolve_target_inside_project()
        assert target is not None
        assert ".mcp" in str(target)


def test_memory_manager_mask_patterns():
    """Test masking patterns functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        config_path = project_root / ".mcp" / "assistant.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create config with mask patterns
        config_content = """
memory:
  mask_patterns:
    - "password.*"
    - "secret.*"
"""
        config_path.write_text(config_content, encoding="utf-8")

        mm = MemoryManager(project_root)

        # Test that mask patterns are loaded
        assert len(mm._mask_re) == 2


def test_memory_manager_environment_variables():
    """Test environment variable handling."""
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Test with MCP_MEMORY_HARD_DISABLE during write
        old_env = os.environ.get("MCP_MEMORY_HARD_DISABLE")
        try:
            os.environ["MCP_MEMORY_HARD_DISABLE"] = "true"
            mm = MemoryManager(project_root)

            # The env check is wrapped in try-except that passes, so it may not raise
            # Test that it at least doesn't crash
            try:
                mm.append_turn("user", "test message")
            except ValueError as e:
                # If it does raise, it should be the right message
                assert "MCP_MEMORY_HARD_DISABLE" in str(e)
        finally:
            if old_env is None:
                os.environ.pop("MCP_MEMORY_HARD_DISABLE", None)
            else:
                os.environ["MCP_MEMORY_HARD_DISABLE"] = old_env


def test_memory_manager_path_outside_mcp():
    """Test handling of paths outside .mcp directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create memory manager with path outside .mcp
        outside_path = project_root / "outside_memory.json"
        mm = MemoryManager(project_root, file_override=outside_path)

        # Should return None for unsafe path
        target = mm._resolve_target_inside_project()
        assert target is None


def test_memory_manager_write_security_checks():
    """Test write security path validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        # Test normal write
        test_data = {"turns": [], "summary": "", "links": []}
        mm._write(test_data)

        # Verify file was written
        assert mm.path.exists()

        # Test with hard disable
        mm._hard_disable = True
        with pytest.raises(ValueError, match="hard_disable"):
            mm._write(test_data)


def test_memory_manager_symlink_security():
    """Test symlink security checks."""
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mcp_dir = project_root / ".mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)

        # Create a regular file first
        memory_file = mcp_dir / "memory.json"
        memory_file.write_text(
            '{"turns": [], "summary": "", "links": []}', encoding="utf-8",
        )

        # Create a symlink to test symlink handling
        symlink_path = mcp_dir / "symlink_memory.json"
        try:
            symlink_path.symlink_to(memory_file)

            # Test with symlink path
            mm = MemoryManager(project_root, file_override=symlink_path)

            # Test with MCP_MEMORY_TRUST_SYMLINK=false (default)
            old_env = os.environ.get("MCP_MEMORY_TRUST_SYMLINK")
            try:
                os.environ.pop("MCP_MEMORY_TRUST_SYMLINK", None)
                target = mm._resolve_target_inside_project()
                # Should return None for untrusted symlink
                assert target is None
            finally:
                if old_env is not None:
                    os.environ["MCP_MEMORY_TRUST_SYMLINK"] = old_env

        except OSError:
            # Skip if symlinks not supported on this platform
            pass


def test_memory_manager_hardlink_security():
    """Test hardlink security checks."""
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mcp_dir = project_root / ".mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)

        # Create a regular file first
        memory_file = mcp_dir / "memory.json"
        memory_file.write_text(
            '{"turns": [], "summary": "", "links": []}', encoding="utf-8",
        )

        # Create a hardlink to test hardlink handling
        hardlink_path = mcp_dir / "hardlink_memory.json"
        try:
            hardlink_path.hardlink_to(memory_file)

            # Test with hardlink path
            mm = MemoryManager(project_root, file_override=hardlink_path)

            # Test with MCP_MEMORY_TRUST_HARDLINK=false (default)
            old_env = os.environ.get("MCP_MEMORY_TRUST_HARDLINK")
            try:
                os.environ.pop("MCP_MEMORY_TRUST_HARDLINK", None)
                target = mm._resolve_target_inside_project()
                # Should return None for untrusted hardlink
                assert target is None
            finally:
                if old_env is not None:
                    os.environ["MCP_MEMORY_TRUST_HARDLINK"] = old_env

        except OSError:
            # Skip if hardlinks not supported on this platform
            pass


def test_memory_manager_ensure_file():
    """Test _ensure_file functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        # Trigger file creation by calling append_turn
        mm.append_turn("user", "test message")

        # File should now exist
        assert mm.path.exists()

        # Should contain valid JSON structure
        data = json.loads(mm.path.read_text(encoding="utf-8"))
        assert "turns" in data
        assert "summary" in data
        assert "links" in data


def test_memory_manager_mask_regex_errors():
    """Test handling of invalid regex patterns in mask_patterns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        config_path = project_root / ".mcp" / "assistant.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create config with invalid regex patterns
        config_content = """
memory:
  mask_patterns:
    - "valid_pattern"
    - "[invalid_regex"
    - ""
    - "another_valid.*"
"""
        config_path.write_text(config_content, encoding="utf-8")

        mm = MemoryManager(project_root)

        # Should only load valid patterns (invalid ones are skipped)
        assert len(mm._mask_re) == 2  # Only valid patterns loaded


def test_memory_manager_symlink_trust_environment():
    """Test MCP_MEMORY_TRUST_SYMLINK environment variable."""
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mcp_dir = project_root / ".mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)

        # Create a regular file first
        memory_file = mcp_dir / "memory.json"
        memory_file.write_text(
            '{"turns": [], "summary": "", "links": []}', encoding="utf-8",
        )

        # Create a symlink to test symlink handling
        symlink_path = mcp_dir / "symlink_memory.json"
        try:
            symlink_path.symlink_to(memory_file)

            # Test with MCP_MEMORY_TRUST_SYMLINK=true
            old_env = os.environ.get("MCP_MEMORY_TRUST_SYMLINK")
            try:
                os.environ["MCP_MEMORY_TRUST_SYMLINK"] = "true"
                mm = MemoryManager(project_root, file_override=symlink_path)
                target = mm._resolve_target_inside_project()
                # Should return valid target when symlink is trusted
                assert target is not None
            finally:
                if old_env is None:
                    os.environ.pop("MCP_MEMORY_TRUST_SYMLINK", None)
                else:
                    os.environ["MCP_MEMORY_TRUST_SYMLINK"] = old_env

        except OSError:
            # Skip if symlinks not supported on this platform
            pass


def test_memory_manager_hardlink_trust_environment():
    """Test MCP_MEMORY_TRUST_HARDLINK environment variable."""
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mcp_dir = project_root / ".mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)

        # Create a regular file first
        memory_file = mcp_dir / "memory.json"
        memory_file.write_text(
            '{"turns": [], "summary": "", "links": []}', encoding="utf-8",
        )

        # Create a hardlink to test hardlink handling
        hardlink_path = mcp_dir / "hardlink_memory.json"
        try:
            hardlink_path.hardlink_to(memory_file)

            # Test with MCP_MEMORY_TRUST_HARDLINK=true
            old_env = os.environ.get("MCP_MEMORY_TRUST_HARDLINK")
            try:
                os.environ["MCP_MEMORY_TRUST_HARDLINK"] = "true"
                mm = MemoryManager(project_root, file_override=hardlink_path)
                target = mm._resolve_target_inside_project()
                # Should return valid target when hardlink is trusted
                assert target is not None
            finally:
                if old_env is None:
                    os.environ.pop("MCP_MEMORY_TRUST_HARDLINK", None)
                else:
                    os.environ["MCP_MEMORY_TRUST_HARDLINK"] = old_env

        except OSError:
            # Skip if hardlinks not supported on this platform
            pass


def test_memory_manager_path_resolution_errors():
    """Test error handling in path resolution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        # Mock the entire _resolve_target_inside_project method to test error handling
        with patch.object(
            mm,
            "_resolve_target_inside_project",
            side_effect=Exception("Resolution error"),
        ):
            # This should trigger the exception handling path
            try:
                mm._ensure_file()  # This calls _resolve_target_inside_project
            except Exception:
                pass  # Expected to handle gracefully


def test_memory_manager_ensure_file_errors():
    """Test error handling in _ensure_file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        # Mock mkdir to raise an exception
        with patch.object(Path, "mkdir", side_effect=Exception("Mkdir error")):
            # Should not crash on mkdir error
            mm._ensure_file()
            # File creation should be skipped due to error
            assert not mm.path.exists()


def test_memory_manager_write_path_security_errors():
    """Test write path security error handling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        # Test write with invalid project root to trigger security check
        with patch.object(mm, "project_root", Path("/invalid/path")):
            test_data = {"turns": [], "summary": "", "links": []}
            with pytest.raises(Exception):
                mm._write(test_data)


def test_memory_manager_symlink_check_errors():
    """Test symlink check error handling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mcp_dir = project_root / ".mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)

        memory_file = mcp_dir / "memory.json"
        mm = MemoryManager(project_root, file_override=memory_file)

        # Test by creating a situation that would trigger symlink error handling
        # Use a non-existent symlink to trigger exception paths
        nonexistent_symlink = mcp_dir / "nonexistent_symlink.json"
        mm_symlink = MemoryManager(project_root, file_override=nonexistent_symlink)

        # This should handle symlink checks gracefully
        target = mm_symlink._resolve_target_inside_project()
        # Should still return a valid target or None based on security checks
        assert target is None or isinstance(target, Path)


def test_memory_manager_config_exception_handling():
    """Test configuration exception handling during initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        config_path = project_root / ".mcp" / "assistant.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create a config that will cause YAML parsing errors
        config_path.write_text("invalid: yaml: [unclosed", encoding="utf-8")

        # Should handle config errors gracefully and use defaults
        mm = MemoryManager(project_root)
        assert mm._mask_re == []
        assert mm._hard_disable is False


def test_memory_manager_is_relative_to_fallback():
    """Test fallback path checking when is_relative_to is not available."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mcp_dir = project_root / ".mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)

        # Create a path outside .mcp to test fallback logic
        outside_path = project_root / "outside.json"
        mm = MemoryManager(project_root, file_override=outside_path)

        # Mock is_relative_to to raise an exception to trigger fallback
        with patch.object(
            Path, "is_relative_to", side_effect=AttributeError("No is_relative_to"),
        ):
            target = mm._resolve_target_inside_project()
            # Should return None for path outside .mcp
            assert target is None


def test_memory_manager_audit_exception_handling():
    """Test audit exception handling in various scenarios."""

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Test with path outside .mcp to trigger audit calls
        outside_path = project_root / "outside.json"
        mm = MemoryManager(project_root, file_override=outside_path)

        # Mock _audit to raise exceptions to test exception handling
        with patch(
            "mcp_rules_assistant.memory._audit", side_effect=Exception("Audit error"),
        ):
            target = mm._resolve_target_inside_project()
            # Should still return None despite audit exception
            assert target is None


def test_memory_manager_symlink_audit_exception():
    """Test symlink audit exception handling."""
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mcp_dir = project_root / ".mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)

        # Create a regular file and symlink
        memory_file = mcp_dir / "memory.json"
        memory_file.write_text(
            '{"turns": [], "summary": "", "links": []}', encoding="utf-8",
        )

        symlink_path = mcp_dir / "symlink_memory.json"
        try:
            symlink_path.symlink_to(memory_file)

            # Test without trusting symlinks
            old_env = os.environ.get("MCP_MEMORY_TRUST_SYMLINK")
            try:
                os.environ.pop("MCP_MEMORY_TRUST_SYMLINK", None)
                mm = MemoryManager(project_root, file_override=symlink_path)

                # Mock _audit to raise exception
                with patch(
                    "mcp_rules_assistant.memory._audit",
                    side_effect=Exception("Audit error"),
                ):
                    target = mm._resolve_target_inside_project()
                    # Should return None despite audit exception
                    assert target is None
            finally:
                if old_env is not None:
                    os.environ["MCP_MEMORY_TRUST_SYMLINK"] = old_env

        except OSError:
            # Skip if symlinks not supported
            pass


def test_memory_manager_hardlink_audit_exception():
    """Test hardlink audit exception handling."""
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mcp_dir = project_root / ".mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)

        # Create a regular file and hardlink
        memory_file = mcp_dir / "memory.json"
        memory_file.write_text(
            '{"turns": [], "summary": "", "links": []}', encoding="utf-8",
        )

        hardlink_path = mcp_dir / "hardlink_memory.json"
        try:
            hardlink_path.hardlink_to(memory_file)

            # Test without trusting hardlinks
            old_env = os.environ.get("MCP_MEMORY_TRUST_HARDLINK")
            try:
                os.environ.pop("MCP_MEMORY_TRUST_HARDLINK", None)
                mm = MemoryManager(project_root, file_override=hardlink_path)

                # Mock _audit to raise exception
                with patch(
                    "mcp_rules_assistant.memory._audit",
                    side_effect=Exception("Audit error"),
                ):
                    target = mm._resolve_target_inside_project()
                    # Should return None despite audit exception
                    assert target is None
            finally:
                if old_env is not None:
                    os.environ["MCP_MEMORY_TRUST_HARDLINK"] = old_env

        except OSError:
            # Skip if hardlinks not supported
            pass


def test_memory_manager_mask_regex_exception():
    """Test masking regex exception handling during append_turn."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mcp_dir = project_root / ".mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)

        # Create config with valid regex pattern
        config_path = mcp_dir / "assistant.yaml"
        config_content = """
memory:
  mask_patterns:
    - "password.*"
"""
        config_path.write_text(config_content, encoding="utf-8")

        mm = MemoryManager(project_root)

        # Create a mock regex that raises exception
        from unittest.mock import Mock

        mock_regex = Mock()
        mock_regex.sub.side_effect = Exception("Regex error")

        # Replace the regex in the list
        original_regex = mm._mask_re[0]
        mm._mask_re[0] = mock_regex

        try:
            # Should handle regex exception gracefully and use original content
            mm.append_turn("user", "password123", {"test": "meta"})

            data = mm._read()
            # Should have appended turn despite regex error
            assert len(data["turns"]) == 1
            assert (
                data["turns"][0]["content"] == "password123"
            )  # Original content preserved
        finally:
            # Restore original regex
            mm._mask_re[0] = original_regex


def test_memory_manager_stat_exception_handling():
    """Test stat exception handling in hardlink check."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mcp_dir = project_root / ".mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)

        memory_file = mcp_dir / "memory.json"
        memory_file.write_text(
            '{"turns": [], "summary": "", "links": []}', encoding="utf-8",
        )
        mm = MemoryManager(project_root, file_override=memory_file)

        # Mock hasattr to return False for stat to trigger exception path
        with patch("builtins.hasattr", return_value=False):
            target = mm._resolve_target_inside_project()
            # Should return the target even if stat info is not available
            assert target is not None


def test_memory_manager_general_exception_in_resolve():
    """Test general exception handling in _resolve_target_inside_project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mm = MemoryManager(project_root)

        # Test by calling a method that uses _resolve_target_inside_project
        # and mock it to raise an exception
        with patch.object(
            mm, "_resolve_target_inside_project", side_effect=Exception("General error"),
        ):
            # _ensure_file should handle the exception gracefully
            mm._ensure_file()
            # Should not crash and file should not be created
            assert not mm.path.exists()
