"""Test nl.py exception handling for coverage completion."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from mcp_rules_assistant import nl


def test_nl_parse_exception_in_external_loading():
    """Test exception handling during external synonym loading to cover lines 128-129."""
    # Reset the global flag
    if "_EXT_LOADED" in nl.__dict__:
        del nl.__dict__["_EXT_LOADED"]

    # Mock Path.cwd() to raise an exception during the loading process
    with patch("pathlib.Path.cwd") as mock_cwd:
        mock_cwd.side_effect = RuntimeError("Simulated filesystem error")

        # Should not crash despite the exception
        result = nl.parse("生成CI")
        # Should still work with built-in synonyms
        assert result == "ci.generate"


def test_nl_parse_exception_in_globals_access():
    """Test exception handling when globals() access fails."""
    # Reset the global flag
    if "_EXT_LOADED" in nl.__dict__:
        del nl.__dict__["_EXT_LOADED"]

    # Patch globals to raise an exception
    original_globals = globals

    def mock_globals_with_error():
        # Allow the first call (for checking _EXT_LOADED), then fail
        if not hasattr(mock_globals_with_error, "call_count"):
            mock_globals_with_error.call_count = 0
        mock_globals_with_error.call_count += 1
        if mock_globals_with_error.call_count > 2:
            raise RuntimeError("Simulated globals error")
        return original_globals()

    # This will test the outer exception handler
    with patch("builtins.globals", side_effect=mock_globals_with_error):
        # Should handle the exception gracefully
        result = nl.parse("生成CI")
        # Should still return the built-in synonym
        assert result == "ci.generate"


def test_nl_parse_exception_with_corrupted_module_state():
    """Test handling when module state is corrupted."""
    # Save original state
    original_synonyms = nl.SYNONYMS.copy()

    try:
        # Reset flag
        if "_EXT_LOADED" in nl.__dict__:
            del nl.__dict__["_EXT_LOADED"]

        # Mock Path operations to cause exception during file operations
        with patch.object(
            Path, "exists", side_effect=Exception("Filesystem corrupted")
        ):
            # Should not crash
            result = nl.parse("生成CI")
            assert result == "ci.generate"
    finally:
        # Restore original state
        nl.SYNONYMS.clear()
        nl.SYNONYMS.update(original_synonyms)


def test_nl_parse_yaml_safe_load_exception():
    """Test exception handling when yaml.safe_load fails."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        mcp_dir = tmppath / ".mcp"
        mcp_dir.mkdir()

        # Create a file that will cause yaml.safe_load to fail
        synonyms_file = mcp_dir / "nl_synonyms.yaml"
        # Write bytes that are not valid UTF-8 to cause encoding error
        synonyms_file.write_bytes(b"\xff\xfe invalid utf-8")

        # Reset flag
        if "_EXT_LOADED" in nl.__dict__:
            del nl.__dict__["_EXT_LOADED"]

        with patch("pathlib.Path.cwd", return_value=tmppath):
            # Should handle the exception and not crash
            result = nl.parse("生成CI")
            assert result == "ci.generate"
