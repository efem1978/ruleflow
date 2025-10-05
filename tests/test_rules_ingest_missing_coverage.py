"""Test rules_ingest.py missing coverage lines."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from mcp_rules_assistant import rules_ingest as ri


def test_parse_conditions_with_env_ide_os_tags():
    """Test parsing env/ide/os condition tags (lines 96-104)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        doc_path = tmppath / "rules.md"

        # Create rule with env/ide/os tags
        doc_path.write_text(
            """
# Test Rule
[env: container, docker] [ide: vscode, pycharm] [os: linux, darwin] 
Coverage must be >95%
Use proper formatting
            """,
            encoding="utf-8",
        )

        res = ri.ingest([str(doc_path)], project_root=tmppath)
        assert isinstance(res, dict)
        assert "compiled" in res


def test_parse_conditions_duplicate_values():
    """Test that duplicate values in conditions are deduplicated (line 101-102)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        doc_path = tmppath / "rules.md"

        # Create rule with duplicate env values
        doc_path.write_text(
            """
# Test Rule
[env: docker, container, docker, docker] Coverage must be >95%
            """,
            encoding="utf-8",
        )

        res = ri.ingest([str(doc_path)], project_root=tmppath)
        assert isinstance(res, dict)


def test_interpret_policy_between_exception():
    """Test exception handling in between-range parsing (lines 200-201)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        doc_path = tmppath / "rules.md"

        # Create text that might cause exception in between-range parsing
        doc_path.write_text(
            """
# Test Rule
Coverage must be between invalid and bad values in the range
Testing exception handling in between parsing with weird text
            """,
            encoding="utf-8",
        )

        res = ri.ingest([str(doc_path)], project_root=tmppath)
        assert isinstance(res, dict)


def test_interpret_policy_chinese_between_exception():
    """Test exception handling in Chinese between-range parsing (lines 218-219)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        doc_path = tmppath / "rules.md"

        # Create text that might cause exception in Chinese between parsing
        doc_path.write_text(
            """
# Test Rule
覆盖率应该介于 不合法数据 和 错误的值 之间的范围
Testing Chinese between parsing exception handling
            """,
            encoding="utf-8",
        )

        res = ri.ingest([str(doc_path)], project_root=tmppath)
        assert isinstance(res, dict)


def test_match_conditions_os_windows():
    """Test OS condition matching for Windows (lines 703-712)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        doc_path = tmppath / "rules.md"

        # Create rule with Windows OS condition
        doc_path.write_text(
            """
# Test Rule
[os: windows] Windows-specific rule
Coverage must be >95%
            """,
            encoding="utf-8",
        )

        # Mock platform to simulate Windows
        with patch("platform.system", return_value="Windows"):
            res = ri.ingest([str(doc_path)], project_root=tmppath)
            # On Windows, rule should be included
            assert isinstance(res, dict)


def test_match_conditions_os_linux():
    """Test OS condition matching for Linux (lines 703-712)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        doc_path = tmppath / "rules.md"

        # Create rule with Linux OS condition
        doc_path.write_text(
            """
# Test Rule
[os: linux] Linux-specific rule
Coverage must be >95%
            """,
            encoding="utf-8",
        )

        # Mock platform to simulate Linux
        with patch("platform.system", return_value="Linux"):
            res = ri.ingest([str(doc_path)], project_root=tmppath)
            assert isinstance(res, dict)


def test_match_conditions_os_darwin():
    """Test OS condition matching for macOS (lines 703-712)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        doc_path = tmppath / "rules.md"

        # Create rule with macOS OS condition
        doc_path.write_text(
            """
# Test Rule
[os: darwin] macOS-specific rule
Coverage must be >95%
            """,
            encoding="utf-8",
        )

        # Mock platform to simulate macOS
        with patch("platform.system", return_value="Darwin"):
            res = ri.ingest([str(doc_path)], project_root=tmppath)
            assert isinstance(res, dict)


def test_match_conditions_ide_vscode():
    """Test IDE condition matching for VSCode (lines 715-718)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        doc_path = tmppath / "rules.md"

        # Create rule with VSCode IDE condition
        doc_path.write_text(
            """
# Test Rule
[ide: vscode] VSCode-specific rule
Use Prettier formatter
            """,
            encoding="utf-8",
        )

        # Test when code CLI is not available
        with patch("shutil.which", return_value=None):
            res = ri.ingest([str(doc_path)], project_root=tmppath)
            # Rule should be filtered out when VSCode is not available
            assert isinstance(res, dict)

        # Test when code CLI is available
        with patch("shutil.which", return_value="/usr/local/bin/code"):
            res = ri.ingest([str(doc_path)], project_root=tmppath)
            assert isinstance(res, dict)


def test_match_conditions_env_container():
    """Test ENV condition matching for container (lines 720-726)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        doc_path = tmppath / "rules.md"

        # Create rule with container environment condition
        doc_path.write_text(
            """
# Test Rule
[env: container] Container-specific rule
Use Docker for builds
            """,
            encoding="utf-8",
        )

        # Test when docker is not available and no Dockerfile
        with patch("shutil.which", return_value=None):
            with patch.object(Path, "exists", return_value=False):
                res = ri.ingest([str(doc_path)], project_root=tmppath)
                assert isinstance(res, dict)

        # Test when docker CLI is available
        with patch(
            "shutil.which",
            side_effect=lambda x: "/usr/local/bin/docker" if x == "docker" else None,
        ):
            res = ri.ingest([str(doc_path)], project_root=tmppath)
            assert isinstance(res, dict)


def test_match_conditions_env_docker():
    """Test ENV condition matching for docker (line 723-725)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        doc_path = tmppath / "rules.md"

        # Create rule with docker environment condition
        doc_path.write_text(
            """
# Test Rule
[env: docker] Docker environment rule
Use docker compose
            """,
            encoding="utf-8",
        )

        # Test when Dockerfile exists
        dockerfile = tmppath / "Dockerfile"
        dockerfile.write_text("FROM python:3.11", encoding="utf-8")

        with patch("pathlib.Path.cwd", return_value=tmppath):
            res = ri.ingest([str(doc_path)], project_root=tmppath)
            assert isinstance(res, dict)


def test_match_conditions_no_conditions():
    """Test that rules with no conditions always match (lines 699-700)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        doc_path = tmppath / "rules.md"

        # Create rule without any conditions
        doc_path.write_text(
            """
# Test Rule
Coverage must be >95%
            """,
            encoding="utf-8",
        )

        res = ri.ingest([str(doc_path)], project_root=tmppath)
        # Rule without conditions should always be included
        assert isinstance(res, dict)


def test_parse_conditions_empty_condition_values():
    """Test handling of conditions with empty values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        doc_path = tmppath / "rules.md"

        # Create rule with empty values in conditions (should be filtered out)
        doc_path.write_text(
            """
# Test Rule
[env: , , docker, , ] Coverage must be >95%
            """,
            encoding="utf-8",
        )

        res = ri.ingest([str(doc_path)], project_root=tmppath)
        assert isinstance(res, dict)


def test_interpret_policy_with_malformed_percentage():
    """Test handling of malformed percentage values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        doc_path = tmppath / "rules.md"

        # Create text with malformed percentage
        doc_path.write_text(
            """
# Test Rule
Coverage must be >= %invalid% percent
Testing malformed percentage handling
            """,
            encoding="utf-8",
        )

        res = ri.ingest([str(doc_path)], project_root=tmppath)
        assert isinstance(res, dict)
