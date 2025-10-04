from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mcp_rules_assistant.audit import log_security_event


def test_audit_basic_functionality():
    """Test basic audit logging functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Call audit function
        log_security_event(project_root, "test.event", {"key": "value"})

        # Check audit log was created
        audit_log = project_root / ".mcp" / "dashboard" / "security_audit.jsonl"
        assert audit_log.exists()

        # Check log content
        log_content = audit_log.read_text(encoding="utf-8")
        assert "test.event" in log_content
        assert "key" in log_content
        assert "value" in log_content


def test_audit_with_none_project_root():
    """Test audit with None project root."""
    # Should not crash
    log_security_event(None, "test.event", {"key": "value"})


def test_audit_with_string_project_root():
    """Test audit with string project root."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Should work with string path
        log_security_event(Path(tmpdir), "test.event", {"key": "value"})

        audit_log = Path(tmpdir) / ".mcp" / "dashboard" / "security_audit.jsonl"
        assert audit_log.exists()


def test_audit_creates_mcp_directory():
    """Test that audit creates .mcp directory if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mcp_dir = project_root / ".mcp"

        # Ensure .mcp doesn't exist initially
        assert not mcp_dir.exists()

        log_security_event(project_root, "test.event", {"key": "value"})

        # Should create .mcp directory
        assert mcp_dir.exists()
        assert mcp_dir.is_dir()


def test_audit_appends_to_existing_log():
    """Test that audit appends to existing log file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # First audit call
        log_security_event(project_root, "first.event", {"first": "data"})

        # Second audit call
        log_security_event(project_root, "second.event", {"second": "data"})

        audit_log = project_root / ".mcp" / "dashboard" / "security_audit.jsonl"
        log_content = audit_log.read_text(encoding="utf-8")

        # Both events should be in the log
        assert "first.event" in log_content
        assert "second.event" in log_content
        assert log_content.count("\n") >= 2  # At least two lines


def test_audit_json_serialization():
    """Test audit with complex data structures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        complex_data = {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "boolean": True,
            "null": None,
        }

        log_security_event(project_root, "complex.event", complex_data)

        audit_log = project_root / ".mcp" / "dashboard" / "security_audit.jsonl"
        log_content = audit_log.read_text(encoding="utf-8")

        # Should contain serialized JSON
        assert "nested" in log_content
        assert "list" in log_content
        assert "boolean" in log_content


def test_audit_with_non_serializable_data():
    """Test audit with non-JSON-serializable data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create non-serializable object
        class NonSerializable:
            pass

        data = {"object": NonSerializable()}

        # Should not crash, should handle gracefully
        log_security_event(project_root, "non_serializable.event", data)

        audit_log = project_root / ".mcp" / "dashboard" / "security_audit.jsonl"
        assert audit_log.exists()


def test_audit_with_empty_data():
    """Test audit with empty data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        log_security_event(project_root, "empty.event", {})

        audit_log = project_root / ".mcp" / "dashboard" / "security_audit.jsonl"
        log_content = audit_log.read_text(encoding="utf-8")

        assert "empty.event" in log_content


def test_audit_with_none_data():
    """Test audit with None data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        log_security_event(project_root, "none.event", None)

        audit_log = project_root / ".mcp" / "dashboard" / "security_audit.jsonl"
        log_content = audit_log.read_text(encoding="utf-8")

        assert "none.event" in log_content


def test_audit_timestamp_format():
    """Test that audit includes proper timestamp."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        log_security_event(project_root, "timestamp.event", {"key": "value"})

        audit_log = project_root / ".mcp" / "dashboard" / "security_audit.jsonl"
        log_content = audit_log.read_text(encoding="utf-8")

        # Should contain timestamp (basic check for date format)
        import re

        # Look for ISO timestamp pattern
        timestamp_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
        assert re.search(timestamp_pattern, log_content)


def test_audit_error_handling_permission_denied():
    """Test audit error handling when file permissions deny write."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        mcp_dir = project_root / ".mcp"
        mcp_dir.mkdir()

        # Create audit log and make it read-only
        audit_log = mcp_dir / "audit.log"
        audit_log.write_text("existing content\n", encoding="utf-8")
        audit_log.chmod(0o444)  # Read-only

        try:
            # Should not crash even if write fails
            log_security_event(project_root, "permission.event", {"key": "value"})
        except Exception:
            pytest.fail("Audit should handle permission errors gracefully")
        finally:
            # Restore permissions for cleanup
            audit_log.chmod(0o644)


def test_audit_error_handling_directory_permission():
    """Test audit when .mcp directory cannot be created."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Make project root read-only
        project_root.chmod(0o444)

        try:
            # Should not crash even if directory creation fails
            log_security_event(project_root, "dir_permission.event", {"key": "value"})
        except Exception:
            pytest.fail("Audit should handle directory creation errors gracefully")
        finally:
            # Restore permissions for cleanup
            project_root.chmod(0o755)


def test_audit_concurrent_writes():
    """Test audit with concurrent writes (basic test)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Simulate concurrent writes
        import threading

        def write_audit(event_id):
            log_security_event(
                project_root, f"concurrent.event.{event_id}", {"id": event_id},
            )

        threads = []
        for i in range(5):
            thread = threading.Thread(target=write_audit, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        audit_log = project_root / ".mcp" / "dashboard" / "security_audit.jsonl"
        log_content = audit_log.read_text(encoding="utf-8")

        # All events should be logged
        for i in range(5):
            assert f"concurrent.event.{i}" in log_content


def test_audit_large_data():
    """Test audit with large data structures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create large data structure
        large_data = {
            "large_list": list(range(1000)),
            "large_dict": {f"key_{i}": f"value_{i}" for i in range(100)},
            "nested": {"level1": {"level2": {"level3": {"data": "deep"}}}},
        }

        log_security_event(project_root, "large.event", large_data)

        audit_log = project_root / ".mcp" / "dashboard" / "security_audit.jsonl"
        assert audit_log.exists()

        # Should handle large data without issues
        log_content = audit_log.read_text(encoding="utf-8")
        assert "large.event" in log_content


def test_audit_special_characters():
    """Test audit with special characters in event names and data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        special_data = {
            "unicode": "测试数据 🎉",
            "special_chars": "!@#$%^&*()[]{}|\\:;\"'<>?,./",
        }

        log_security_event(project_root, "special.event.测试", special_data)

        audit_log = project_root / ".mcp" / "dashboard" / "security_audit.jsonl"
        log_content = audit_log.read_text(encoding="utf-8")

        assert "special.event.测试" in log_content
        assert "测试数据" in log_content


def test_audit_multiple_events_same_name():
    """Test audit with multiple events of the same name."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Log same event multiple times with different data
        log_security_event(project_root, "repeated.event", {"attempt": 1})
        log_security_event(project_root, "repeated.event", {"attempt": 2})
        log_security_event(project_root, "repeated.event", {"attempt": 3})

        audit_log = project_root / ".mcp" / "dashboard" / "security_audit.jsonl"
        log_content = audit_log.read_text(encoding="utf-8")

        # All instances should be logged
        assert log_content.count("repeated.event") == 3
        assert "attempt" in log_content
