from __future__ import annotations

from pathlib import Path


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


def test_checks_delegate_enabled_via_config(tmp_path: Path, monkeypatch):
    # No env toggle
    monkeypatch.delenv("MCP_CHECKS_PROCESS_RUNNER", raising=False)

    # Prepare assistant.yaml to enable delegation
    d = tmp_path / ".mcp"
    d.mkdir(parents=True, exist_ok=True)
    (d / "assistant.yaml").write_text(
        """
execution:
  checks_delegate_run_cmd: true
        """.strip(),
        encoding="utf-8",
    )

    import mcp_rules_assistant.checks as checks

    # reset cache and override project root used by _use_process_runner
    checks._USE_PROC_RUNNER_CACHE = None  # type: ignore[attr-defined]

    called = {}

    def _stub_run_cmd(
        cmd, *, cwd, capture_stdout=True, env=None, check=False, **kw,
    ):  # noqa: ARG001
        called["cwd"] = str(cwd)
        return type("P", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    # Point to our temp repo as CWD
    with chdir(tmp_path):
        monkeypatch.setattr(checks, "_proc_run_cmd", _stub_run_cmd, raising=True)
        out = checks._run(["echo"], cwd=tmp_path)
        assert out["ok"] is True
        assert called["cwd"].endswith(str(tmp_path))
