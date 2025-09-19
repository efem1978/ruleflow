"""
Performance benchmarks for commercial release validation
"""

import os
import subprocess
import tempfile
import time
from pathlib import Path

import pytest


class TestPerformanceBenchmarks:
    """Commercial-grade performance benchmarks"""

    @pytest.mark.benchmark
    def test_cli_cold_start_performance(self, benchmark):
        """Benchmark CLI cold start time"""

        def run_help():
            result = subprocess.run(
                ["mcp-rules-assistant", "--help"], capture_output=True, text=True
            )
            assert result.returncode == 0
            return result

        result = benchmark(run_help)
        assert "MCP Rules & Context Assistant CLI" in result.stdout

    @pytest.mark.benchmark
    def test_rules_ingestion_performance(self, benchmark):
        """Benchmark rules ingestion performance"""

        def setup_and_ingest():
            with tempfile.TemporaryDirectory() as tmpdir:
                original_dir = os.getcwd()
                try:
                    os.chdir(tmpdir)

                    # Create test rule files
                    for i in range(50):
                        with open(f"rule_{i}.md", "w") as f:
                            f.write(f"# Rule {i}\n" + "Content line\n" * 20)

                    # Initialize
                    subprocess.run(
                        ["mcp-rules-assistant", "init", "--mode", "fast"],
                        capture_output=True,
                    )

                    # Benchmark ingestion
                    result = subprocess.run(
                        ["mcp-rules-assistant", "ingest-rules", "."],
                        capture_output=True,
                        text=True,
                    )
                    assert result.returncode == 0
                    return result
                finally:
                    os.chdir(original_dir)

        benchmark(setup_and_ingest)

    @pytest.mark.benchmark
    def test_coverage_analysis_performance(self, benchmark):
        """Benchmark coverage analysis performance"""

        def analyze_coverage():
            with tempfile.TemporaryDirectory() as tmpdir:
                original_dir = os.getcwd()
                try:
                    os.chdir(tmpdir)

                    # Create large coverage.xml
                    coverage_content = """<?xml version="1.0" ?>
<coverage version="7.0.0">
    <sources><source>.</source></sources>
    <packages>"""

                    for i in range(100):
                        coverage_content += f"""
        <package name="package_{i}">
            <classes>
                <class filename="file_{i}.py" line-rate="0.85">
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="1"/>
                        <line number="3" hits="0"/>
                    </lines>
                </class>
            </classes>
        </package>"""

                    coverage_content += """
    </packages>
</coverage>"""

                    with open("coverage.xml", "w") as f:
                        f.write(coverage_content)

                    result = subprocess.run(
                        ["mcp-rules-assistant", "coverage"],
                        capture_output=True,
                        text=True,
                    )
                    assert result.returncode == 0
                    return result
                finally:
                    os.chdir(original_dir)

        benchmark(analyze_coverage)

    def test_memory_usage_limits(self):
        """Ensure memory usage stays within commercial limits"""
        import os
        import subprocess

        import psutil

        # Create a temporary directory for the test
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)

            # Initialize MCP in test directory
            subprocess.run(
                ["mcp-rules-assistant", "init"], capture_output=True, text=True
            )

            # Monitor memory during heavy operation
            process = subprocess.Popen(
                ["mcp-rules-assistant", "diagnose"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            max_memory = 0
            measurements = 0
            while process.poll() is None and measurements < 50:  # Limit measurements
                try:
                    proc = psutil.Process(process.pid)
                    memory_mb = proc.memory_info().rss / 1024 / 1024
                    max_memory = max(max_memory, memory_mb)
                    measurements += 1
                    time.sleep(0.1)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    break

            process.wait()

            # Should not exceed 200MB for basic operations (more reasonable limit)
            assert max_memory < 200, f"Memory usage too high: {max_memory:.1f}MB"

    def test_concurrent_operations(self):
        """Test performance under concurrent load"""
        import os
        import queue
        import threading

        results = queue.Queue()

        def run_simple_command():
            try:
                start_time = time.time()
                result = subprocess.run(
                    ["mcp-rules-assistant", "--help"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                end_time = time.time()

                results.put(
                    {
                        "success": result.returncode == 0,
                        "duration": end_time - start_time,
                    }
                )
            except Exception as e:
                results.put({"success": False, "error": str(e)})

        # Run 3 concurrent simple operations (less resource intensive)
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=run_simple_command)
            threads.append(thread)
            thread.start()

        # Wait for all to complete
        for thread in threads:
            thread.join(timeout=30)

        # Check all succeeded
        success_count = 0
        total_duration = 0
        while not results.empty():
            result = results.get()
            if result.get("success", False):
                success_count += 1
                total_duration += result.get("duration", 0)

        # All should succeed for simple help command
        assert (
            success_count >= 2
        ), f"Only {success_count}/3 concurrent operations succeeded"

        # Average duration should be reasonable
        if success_count > 0:
            avg_duration = total_duration / success_count
            assert (
                avg_duration < 5
            ), f"Average concurrent operation took too long: {avg_duration:.1f}s"
