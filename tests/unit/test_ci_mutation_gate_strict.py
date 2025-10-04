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


def test_ci_mutation_step_contains_conditional_block(tmp_path: Path) -> None:
    """When mutation is enabled by rules, CI YAML includes conditional strict gate shell."""
    runner = CliRunner()
    with chdir(tmp_path):
        d = tmp_path / ".mcp"
        d.mkdir(parents=True, exist_ok=True)
        # Enable mutation via compiled rules
        (d / "rules_compiled.json").write_text(
            '{"policy": {"test.mutation_required": true}}', encoding="utf-8",
        )
        r = runner.invoke(app, ["generate-ci"])
        assert r.exit_code == 0
        yml = (tmp_path / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        assert "Mutation testing" in yml
        # Should contain conditional grep for strict/flag
        assert "grep -Eq" in yml and "mode:" in yml and "mutation_gate_strict" in yml
        # Should contain fallback non-blocking branch as well
        assert "mutmut run -q || true" in yml


def test_ci_mutation_step_under_strict_mode(tmp_path: Path) -> None:
    runner = CliRunner()
    with chdir(tmp_path):
        d = tmp_path / ".mcp"
        d.mkdir(parents=True, exist_ok=True)
        # Enable mutation via on_push config to trigger step
        (d / "assistant.yaml").write_text(
            """
performance:
  mode: strict
  on_push:
    mutation_test: true
            """.strip(),
            encoding="utf-8",
        )
        r = runner.invoke(app, ["generate-ci"])
        assert r.exit_code == 0
        yml = (tmp_path / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        assert "Mutation testing" in yml
        assert "grep -Eq" in yml and "mode:" in yml
