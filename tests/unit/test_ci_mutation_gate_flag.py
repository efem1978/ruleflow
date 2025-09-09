from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def chdir(path: Path):
    class _Ctx:
        def __enter__(self):
            self._old = Path.cwd()
            import os

            os.chdir(path)
            return path

        def __exit__(self, exc_type, exc, tb):
            import os

            os.chdir(self._old)

    return _Ctx()


def test_ci_mutation_gate_enabled_by_flag_non_strict(tmp_path: Path) -> None:
    runner = CliRunner()
    with chdir(tmp_path):
        d = tmp_path / ".mcp"
        d.mkdir(parents=True, exist_ok=True)
        # Non-strict, but gate flag enabled; enable mutation step via on_push
        (d / "assistant.yaml").write_text(
            """
performance:
  mode: fast
  on_push:
    mutation_test: true
ci:
  mutation_gate_strict: true
            """.strip(),
            encoding="utf-8",
        )
        r = runner.invoke(app, ["generate-ci"])
        assert r.exit_code == 0
        yml = (tmp_path / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        assert "Mutation testing" in yml
        assert "grep -Eq" in yml and "mutation_gate_strict" in yml
