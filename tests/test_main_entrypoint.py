from __future__ import annotations

import sys
from runpy import run_module

import pytest


def test_module_entrypoint_runs_help(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate `python -m mcp_rules_assistant --help` so that
    # mcp_rules_assistant/__main__.py executes the Typer app()
    old_argv = list(sys.argv)
    try:
        sys.argv = ["mcp_rules_assistant", "--help"]
        with pytest.raises(SystemExit) as exc:
            run_module("mcp_rules_assistant.__main__", run_name="__main__")
        # Typer exits with code 0 on --help
        assert int(exc.value.code or 0) == 0
    finally:
        sys.argv = old_argv

