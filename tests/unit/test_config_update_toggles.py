from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


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


def test_config_update_writes_toggles(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    with chdir(tmp_path):
        # Update both toggles
        out = srv._call_tool(
            "config.update",
            {
                "mutation_gate_strict": True,
                "execution": {"checks_delegate_run_cmd": True},
            },
        )
        assert out.get("ok") is True
        # Read back
        res = srv._call_tool("config.get", {})
        cfg = res.get("config", {})
        assert cfg.get("ci", {}).get("mutation_gate_strict") is True
        assert cfg.get("execution", {}).get("checks_delegate_run_cmd") is True
