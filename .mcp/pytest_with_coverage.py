#!/usr/bin/env python3
import os
import platform
import subprocess
import sys
from pathlib import Path


def ensure_plugin(py: str) -> None:
    try:
        __import__("pytest_benchmark")
        return
    except Exception:
        pass
    try:
        subprocess.run(
            [py, "-m", "pip", "install", "-q", "pytest-benchmark"], check=False
        )
    except Exception:
        pass


def main() -> int:
    root = Path(".").resolve()
    venv = root / ".mcp" / "venv"
    bin_dir = venv / (
        "Scripts" if platform.system().lower().startswith("win") else "bin"
    )
    if bin_dir.exists():
        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    vpy = bin_dir / (
        "python.exe" if platform.system().lower().startswith("win") else "python"
    )
    py = str(vpy) if vpy.exists() else sys.executable

    ensure_plugin(py)

    cmd = [
        py,
        "-m",
        "pytest",
        "-q",
        "-p",
        "pytest_cov",
        "-p",
        "pytest_benchmark.plugin",
        "--maxfail=1",
        "--disable-warnings",
        "-W",
        "error",
        "--strict-markers",
        "--cov=mcp_rules_assistant",
        "--cov-report=xml:coverage.xml",
        "--cov-report=term-missing",
        f"--cov-fail-under={_MIN}",
    ]
    r = subprocess.run(cmd)
    return r.returncode


if __name__ == "__main__":
    _MIN = 99
    sys.exit(main())
