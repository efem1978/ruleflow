from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from mcp_rules_assistant import nl


def test_nl_parse_basic_synonyms():
    """Test basic synonym parsing functionality."""
    assert nl.parse("生成CI") == "ci.generate"
    assert nl.parse("校验 ci") == "ci.validate"
    assert nl.parse("开启滚动记忆") == "memory.toggle_auto"
    assert nl.parse("摄取规则") == "rules.ingest"
    assert nl.parse("近阈值") == "coverage.near"
    assert nl.parse("prepare environment") == "env.prepare"


def test_nl_parse_case_insensitive():
    """Test that parsing is case insensitive."""
    assert nl.parse("Generate CI") == "ci.generate"
    assert nl.parse("GENERATE CI") == "ci.generate"
    assert nl.parse("generate ci") == "ci.generate"


def test_nl_parse_whitespace_handling():
    """Test whitespace handling in parsing."""
    assert nl.parse("  生成CI  ") == "ci.generate"
    assert nl.parse("\t校验 ci\n") == "ci.validate"


def test_nl_parse_partial_match():
    """Test partial matching within text."""
    assert nl.parse("请帮我生成CI配置") == "ci.generate"
    assert nl.parse("I need to generate ci workflow") == "ci.generate"


def test_nl_parse_no_match():
    """Test when no synonym matches."""
    assert nl.parse("random text") is None
    assert nl.parse("") is None
    assert nl.parse("   ") is None


def test_nl_parse_memory_commands():
    """Test memory-related commands."""
    assert nl.parse("开启记忆") == "memory.toggle_auto"
    assert nl.parse("关闭记忆") == "memory.toggle_auto"
    assert nl.parse("记忆快照") == "memory.snapshot"
    assert nl.parse("追加记忆") == "memory.append_turn"


def test_nl_parse_rules_commands():
    """Test rules-related commands."""
    assert nl.parse("初始化规则") == "rules.init"
    assert nl.parse("摄取规则") == "rules.ingest"
    assert nl.parse("校验规则") == "rules.validate"
    assert nl.parse("应用门禁") == "rules.enforce"
    assert nl.parse("规则引导") == "rules.onboard"


def test_nl_parse_coverage_commands():
    """Test coverage-related commands."""
    assert nl.parse("加载覆盖率") == "coverage.report"
    assert nl.parse("导出覆盖率") == "coverage.report"
    assert nl.parse("加载近阈值") == "coverage.near"
    assert nl.parse("近阈值") == "coverage.near"


def test_nl_parse_ci_commands():
    """Test CI-related commands."""
    assert nl.parse("生成 ci") == "ci.generate"
    assert nl.parse("生成工作流") == "ci.generate"
    assert nl.parse("校验 ci") == "ci.validate"
    assert nl.parse("自修复 ci") == "ci.autofix"


def test_nl_parse_plan_commands():
    """Test plan-related commands."""
    assert nl.parse("建议下一步") == "plan.suggest_next"
    assert nl.parse("计划 设置") == "plan.set"
    assert nl.parse("计划 更新") == "plan.set"


def test_nl_parse_fs_commands():
    """Test filesystem-related commands."""
    assert nl.parse("受控写入") == "fs.apply_patch"
    assert nl.parse("guarded write") == "fs.apply_patch"
    assert nl.parse("apply patch") == "fs.apply_patch"


def test_nl_parse_external_synonyms_file():
    """Test loading external synonyms from .mcp/nl_synonyms.yaml."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        mcp_dir = tmppath / ".mcp"
        mcp_dir.mkdir()

        # Create external synonyms file
        synonyms_file = mcp_dir / "nl_synonyms.yaml"
        external_synonyms = {
            "custom command": "custom.action",
            "特殊命令": "special.command",
        }
        synonyms_file.write_text(yaml.dump(external_synonyms), encoding="utf-8")

        # Reset the global flag to force reload
        if "_EXT_LOADED" in nl.__dict__:
            del nl.__dict__["_EXT_LOADED"]

        with patch("pathlib.Path.cwd", return_value=tmppath):
            # This should trigger loading of external synonyms
            result = nl.parse("custom command")
            assert result == "custom.action"

            result = nl.parse("特殊命令")
            assert result == "special.command"


def test_nl_parse_external_synonyms_yml_extension():
    """Test loading external synonyms from .mcp/nl_synonyms.yml."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        mcp_dir = tmppath / ".mcp"
        mcp_dir.mkdir()

        # Create external synonyms file with .yml extension
        synonyms_file = mcp_dir / "nl_synonyms.yml"
        external_synonyms = {"yml command": "yml.action"}
        synonyms_file.write_text(yaml.dump(external_synonyms), encoding="utf-8")

        # Reset the global flag
        if "_EXT_LOADED" in nl.__dict__:
            del nl.__dict__["_EXT_LOADED"]

        with patch("pathlib.Path.cwd", return_value=tmppath):
            result = nl.parse("yml command")
            assert result == "yml.action"


def test_nl_parse_external_synonyms_invalid_yaml():
    """Test handling of invalid YAML in external synonyms file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        mcp_dir = tmppath / ".mcp"
        mcp_dir.mkdir()

        # Create invalid YAML file
        synonyms_file = mcp_dir / "nl_synonyms.yaml"
        synonyms_file.write_text("invalid: yaml: content: [", encoding="utf-8")

        # Reset the global flag
        if "_EXT_LOADED" in nl.__dict__:
            del nl.__dict__["_EXT_LOADED"]

        with patch("pathlib.Path.cwd", return_value=tmppath):
            # Should not crash and should still work with built-in synonyms
            result = nl.parse("生成CI")
            assert result == "ci.generate"


def test_nl_parse_external_synonyms_invalid_data_types():
    """Test handling of invalid data types in external synonyms."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        mcp_dir = tmppath / ".mcp"
        mcp_dir.mkdir()

        # Create file with invalid data types
        synonyms_file = mcp_dir / "nl_synonyms.yaml"
        external_synonyms = {
            "valid_key": "valid_value",
            123: "invalid_key_type",  # Invalid key type
            "invalid_value_key": 456,  # Invalid value type
            "": "empty_key",  # Empty key
            "empty_value": "",  # Empty value
            "  ": "whitespace_key",  # Whitespace-only key
            "whitespace_value": "  ",  # Whitespace-only value (should be stripped)
        }
        synonyms_file.write_text(yaml.dump(external_synonyms), encoding="utf-8")

        # Reset the global flag
        if "_EXT_LOADED" in nl.__dict__:
            del nl.__dict__["_EXT_LOADED"]

        with patch("pathlib.Path.cwd", return_value=tmppath):
            # Should only load valid entries
            result = nl.parse("valid_key")
            assert result == "valid_value"

            # whitespace_value should be stripped to empty and not match
            result = nl.parse("whitespace_value")
            # Empty values are filtered out, so this shouldn't match
            assert result is None


def test_nl_parse_external_synonyms_non_dict():
    """Test handling of non-dict data in external synonyms file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        mcp_dir = tmppath / ".mcp"
        mcp_dir.mkdir()

        # Create file with list instead of dict
        synonyms_file = mcp_dir / "nl_synonyms.yaml"
        synonyms_file.write_text("- item1\n- item2", encoding="utf-8")

        # Reset the global flag
        if "_EXT_LOADED" in nl.__dict__:
            del nl.__dict__["_EXT_LOADED"]

        with patch("pathlib.Path.cwd", return_value=tmppath):
            # Should not crash and should still work with built-in synonyms
            result = nl.parse("生成CI")
            assert result == "ci.generate"


def test_nl_parse_external_synonyms_file_not_exists():
    """Test behavior when external synonyms file doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        mcp_dir = tmppath / ".mcp"
        mcp_dir.mkdir()
        # No synonyms file created

        # Reset the global flag
        if "_EXT_LOADED" in nl.__dict__:
            del nl.__dict__["_EXT_LOADED"]

        with patch("pathlib.Path.cwd", return_value=tmppath):
            # Should work with built-in synonyms only
            result = nl.parse("生成CI")
            assert result == "ci.generate"


def test_nl_parse_global_flag_prevents_reload():
    """Test that the global flag prevents reloading external synonyms."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        mcp_dir = tmppath / ".mcp"
        mcp_dir.mkdir()

        # Set the global flag to True
        nl.__dict__["_EXT_LOADED"] = True

        # Create external synonyms file
        synonyms_file = mcp_dir / "nl_synonyms.yaml"
        external_synonyms = {"should_not_load": "not.loaded"}
        synonyms_file.write_text(yaml.dump(external_synonyms), encoding="utf-8")

        with patch("pathlib.Path.cwd", return_value=tmppath):
            # Should not load external synonyms due to flag
            result = nl.parse("should_not_load")
            assert result is None  # Should not find the external synonym


def test_nl_parse_all_built_in_synonyms():
    """Test all built-in synonyms to ensure they work."""
    # Test a representative sample of all categories
    test_cases = [
        # Memory commands
        ("开启滚动记忆", "memory.toggle_auto"),
        ("关闭滚动记忆", "memory.toggle_auto"),
        ("enable rolling memory", "memory.toggle_auto"),
        ("记忆快照", "memory.snapshot"),
        ("snapshot", "memory.snapshot"),
        # Rules/hooks/environment
        ("安装钩子", "git.install_hooks"),
        ("install hooks", "git.install_hooks"),
        ("初始化规则", "rules.init"),
        ("摄取规则", "rules.ingest"),
        ("校验规则", "rules.validate"),
        ("应用门禁", "rules.enforce"),
        # CI commands
        ("生成 ci", "ci.generate"),
        ("generate ci", "ci.generate"),
        ("校验 ci", "ci.validate"),
        ("自修复 ci", "ci.autofix"),
        # Coverage commands
        ("加载覆盖率", "coverage.report"),
        ("load coverage", "coverage.report"),
        ("加载近阈值", "coverage.near"),
        ("near coverage", "coverage.near"),
        # Environment
        ("准备环境", "env.prepare"),
        ("prepare environment", "env.prepare"),
        # Plan commands
        ("建议下一步", "plan.suggest_next"),
        ("next steps", "plan.suggest_next"),
        ("计划 设置", "plan.set"),
        ("plan set", "plan.set"),
        # FS commands
        ("受控写入", "fs.apply_patch"),
        ("guarded write", "fs.apply_patch"),
        ("apply patch", "fs.apply_patch"),
        # Rules summary
        ("规则 摘要", "rules.maxima"),
        ("rules summary", "rules.maxima"),
    ]

    for input_text, expected_output in test_cases:
        result = nl.parse(input_text)
        assert (
            result == expected_output
        ), f"Failed for input '{input_text}': expected '{expected_output}', got '{result}'"
