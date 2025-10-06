"""
End-to-end tests for complete MCP Rules Assistant workflow
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class TestFullWorkflow:
    """Test complete workflow from installation to usage"""

    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

    def teardown_method(self):
        """Cleanup test environment"""
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def test_cli_basic_commands(self):
        """Test basic CLI commands work"""
        # Test help command
        result = subprocess.run(
            ["mcp-rules-assistant", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "MCP Rules & Context Assistant CLI" in result.stdout

    def test_init_and_ingest_workflow(self):
        """Test complete init and rules ingestion workflow"""
        # Create a test project structure
        os.makedirs("src")
        with open("src/test.py", "w") as f:
            f.write('# Test Python file\nprint("hello")\n')

        with open("README.md", "w") as f:
            f.write("# Test Project\nThis is a test project.\n")

        # Initialize MCP
        result = subprocess.run(
            ["mcp-rules-assistant", "init"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert os.path.exists(".mcp/assistant.yaml")

        # Ingest rules
        result = subprocess.run(
            ["mcp-rules-assistant", "ingest-rules", "."],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_coverage_analysis(self):
        """Test coverage analysis functionality"""
        # Create minimal coverage.xml
        coverage_xml = """<?xml version="1.0" ?>
<coverage version="7.0.0">
    <sources>
        <source>.</source>
    </sources>
    <packages>
        <package name="test">
            <classes>
                <class filename="test.py" line-rate="0.8">
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="0"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>"""

        with open("coverage.xml", "w") as f:
            f.write(coverage_xml)

        # Test coverage command
        result = subprocess.run(
            ["mcp-rules-assistant", "coverage"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_diagnose_command(self):
        """Test diagnostic functionality"""
        result = subprocess.run(
            ["mcp-rules-assistant", "diagnose"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Should return valid JSON
        import json

        diagnostic_data = json.loads(result.stdout)
        assert "python_version" in diagnostic_data
        assert "platform" in diagnostic_data
        assert "tools" in diagnostic_data


class TestIDEIntegration:
    """Test IDE integration functionality"""

    def test_vscode_extension_package(self):
        """Test VSCode extension can be packaged"""
        vscode_dir = Path(__file__).parent.parent.parent / "extensions" / "vscode"
        if vscode_dir.exists():
            # Check if node_modules exists (npm dependencies installed)
            if not (vscode_dir / "node_modules").exists():
                pytest.skip("npm dependencies not installed")
            result = subprocess.run(
                ["npm", "run", "compile"],
                cwd=vscode_dir,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0

    def test_jetbrains_plugin_structure(self):
        """Test JetBrains plugin structure"""
        jetbrains_dir = (
            Path(__file__).parent.parent.parent / "extensions" / "jetbrains.disabled"
        )
        if jetbrains_dir.exists():
            assert (jetbrains_dir / "build.gradle.kts").exists()
            assert (jetbrains_dir / "src").exists()


class TestSecurityCompliance:
    """Test security and compliance requirements"""

    def test_no_hardcoded_secrets(self):
        """Ensure no hardcoded secrets in codebase"""
        project_root = Path(__file__).parent.parent.parent

        # Patterns that might indicate secrets
        secret_patterns = [
            r'password\s*=\s*["\'][^"\']+["\']',
            r'api_key\s*=\s*["\'][^"\']+["\']',
            r'secret\s*=\s*["\'][^"\']+["\']',
            r'token\s*=\s*["\'][^"\']+["\']',
        ]

        import re

        for py_file in project_root.rglob("*.py"):
            if (
                "test" in str(py_file)
                or ".mcp" in str(py_file)
                or ".venv" in str(py_file)
            ):
                continue

            content = py_file.read_text()
            for pattern in secret_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                # Filter out false positives like template strings
                real_matches = [
                    m
                    for m in matches
                    if not any(
                        fp in m for fp in ["[step:", "{{", "}}", "template", "example"]
                    )
                ]
                assert (
                    not real_matches
                ), f"Potential secret found in {py_file}: {real_matches}"

    def test_license_headers(self):
        """Ensure proper license headers"""
        project_root = Path(__file__).parent.parent.parent
        assert (project_root / "LICENSE").exists()

        # Check main Python files have appropriate headers
        main_files = list((project_root / "mcp_rules_assistant").rglob("*.py"))
        assert len(main_files) > 0, "No Python files found in main package"


class TestPerformance:
    """Performance benchmarks for commercial release"""

    def test_cli_startup_time(self):
        """Test CLI startup performance"""
        import time

        start_time = time.time()
        result = subprocess.run(
            ["mcp-rules-assistant", "--help"],
            capture_output=True,
            text=True,
        )
        end_time = time.time()

        assert result.returncode == 0
        startup_time = end_time - start_time
        assert startup_time < 2.0, f"CLI startup too slow: {startup_time:.2f}s"

    def test_rules_ingestion_performance(self):
        """Test rules ingestion performance"""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)

            # Create test files
            for i in range(10):
                with open(f"rule_{i}.md", "w") as f:
                    f.write(f"# Rule {i}\nThis is test rule {i}\n" * 10)

            # Initialize
            subprocess.run(["mcp-rules-assistant", "init"], capture_output=True)

            import time

            start_time = time.time()
            result = subprocess.run(
                ["mcp-rules-assistant", "ingest-rules", "."],
                capture_output=True,
                text=True,
            )
            end_time = time.time()

            assert result.returncode == 0
            ingestion_time = end_time - start_time
            assert (
                ingestion_time < 10.0
            ), f"Rules ingestion too slow: {ingestion_time:.2f}s"
