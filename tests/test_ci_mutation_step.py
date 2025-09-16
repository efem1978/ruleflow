from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app
from mcp_rules_assistant.mcp_server import JsonRpcServer


def chdir(path: Path):
    class _Ctx:
        def __enter__(self):
            import os

            try:
                self._old = Path.cwd()
            except (FileNotFoundError, OSError):
                # If current directory doesn't exist, use a safe default
                self._old = Path.home()

            os.chdir(path)
            return path

        def __exit__(self, exc_type, exc, tb):
            import os

            try:
                os.chdir(self._old)
            except (FileNotFoundError, OSError):
                # If original directory was deleted, just continue
                pass

    return _Ctx()


def test_ci_without_mutation_has_no_step(tmp_path: Path) -> None:
    runner = CliRunner()
    with chdir(tmp_path):
        r = runner.invoke(app, ["generate-ci"])
        assert r.exit_code == 0
        yml = (tmp_path / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        assert "mutmut run" not in yml
        srv = JsonRpcServer()
        srv.project_root = tmp_path
        v = srv.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "ci.validate", "arguments": {}},
            }
        )
        checks = v.get("result", {}).get("checks", {})
        assert checks.get("has_mutation") is False


def test_ci_with_rules_mutation_step_present(tmp_path: Path) -> None:
    runner = CliRunner()
    with chdir(tmp_path):
        d = tmp_path / ".mcp"
        d.mkdir(parents=True, exist_ok=True)
        (d / "rules_compiled.json").write_text(
            '{"policy": {"test.mutation_required": true}}', encoding="utf-8"
        )
        r = runner.invoke(app, ["generate-ci"])
        assert r.exit_code == 0
        yml = (tmp_path / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        assert "mutmut run" in yml and "Mutation testing" in yml
        srv = JsonRpcServer()
        srv.project_root = tmp_path
        v = srv.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "ci.validate", "arguments": {}},
            }
        )
        checks = v.get("result", {}).get("checks", {})
        assert checks.get("has_mutation") is True
