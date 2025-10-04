from __future__ import annotations

import os
from pathlib import Path

import yaml

from mcp_rules_assistant.config import ensure_project_config
from mcp_rules_assistant.mcp_server import JsonRpcServer


def chdir(path: Path):
    class _Ctx:
        def __enter__(self):
            self._old = Path.cwd()
            os.chdir(path)
            return path

        def __exit__(self, exc_type, exc, tb):
            os.chdir(self._old)

    return _Ctx()


def test_config_get_and_update(tmp_path: Path):
    with chdir(tmp_path):
        # ensure default project config exists
        ensure_project_config()
        srv = JsonRpcServer()
        # get config
        res = srv._call_tool("config.get", {"section": None})
        assert res.get("ok") is True
        assert isinstance(res.get("config"), dict)

        # update CI-related fields
        upd = srv._call_tool(
            "config.update",
            {
                "data": {
                    "hadolint": True,
                    "hadolint_image": "hadolint/hadolint:latest",
                    "hadolint_args": "--ignore DL3008",
                },
            },
        )
        assert upd.get("ok") is True
        cfg_path = tmp_path / ".mcp/assistant.yaml"
        y = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        assert (y.get("ci", {}) or {}).get("hadolint") is True
        assert (y.get("ci", {}) or {}).get(
            "hadolint_image",
        ) == "hadolint/hadolint:latest"
        assert (y.get("ci", {}) or {}).get("hadolint_args") == "--ignore DL3008"


def test_rules_enforce_updates_coverage_thresholds(tmp_path: Path):
    with chdir(tmp_path):
        ensure_project_config()
        # Prepare compiled rules with coverage thresholds
        compiled_dir = tmp_path / ".mcp"
        compiled_dir.mkdir(parents=True, exist_ok=True)
        (compiled_dir / "rules_compiled.json").write_text(
            ('{"policy": {"coverage.min_module": 0.93, "coverage.min_core": 0.96}}'),
            encoding="utf-8",
        )
        srv = JsonRpcServer()
        out = srv._call_tool("rules.enforce", {})
        assert out.get("ok") is True

        y = (
            yaml.safe_load(
                (tmp_path / ".mcp/assistant.yaml").read_text(encoding="utf-8"),
            )
            or {}
        )
        perf = y.get("performance", {}) or {}
        on_push = perf.get("on_push", {}) or {}
        cov = on_push.get("coverage", {}) or {}
        assert abs(float(cov.get("min_module")) - 0.93) < 1e-6
        assert abs(float(cov.get("min_core")) - 0.96) < 1e-6
