from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from mcp_rules_assistant.mcp_server import JsonRpcServer
from mcp_rules_assistant.config import ensure_project_config


def chdir(path: Path):
    class _Ctx:
        def __enter__(self):
            self._old = Path.cwd()
            os.chdir(path)
            return path

        def __exit__(self, exc_type, exc, tb):
            os.chdir(self._old)

    return _Ctx()


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def _write_cov_xml(path: Path) -> None:
    text = (
        "<coverage>\n"
        "  <packages><package><classes>\n"
        "    <class filename=\"pkg/core.py\" line-rate=\"0.94\" lines-valid=\"100\" lines-covered=\"94\"/>\n"
        "    <class filename=\"other/x.py\" line-rate=\"0.89\" lines-valid=\"100\" lines-covered=\"89\"/>\n"
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )
    path.write_text(text, encoding="utf-8")


def test_mcp_resources_coverage_groups_respects_policy(tmp_path: Path) -> None:
    with chdir(tmp_path):
        ensure_project_config()
        # Set coverage policy and default min_module
        p = tmp_path / ".mcp/assistant.yaml"
        y = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        y.setdefault("coverage", {})["policy"] = {"pkg/": 0.95}
        y.setdefault("performance", {}).setdefault("on_push", {}).setdefault("coverage", {})["min_module"] = 0.90
        p.write_text(yaml.safe_dump(y, sort_keys=False, allow_unicode=True), encoding="utf-8")

        _write_cov_xml(tmp_path / "coverage.xml")
        srv = JsonRpcServer()
        rlist = srv.handle(_req("resources/list"))
        groups_uri = next(r["uri"] for r in rlist["result"]["resources"] if str(r["uri"]).endswith("/groups"))
        r = srv.handle(_req("resources/read", {"uri": groups_uri}))
        assert r.get("result", {}).get("mimeType") == "application/json"
        data = json.loads(r.get("result", {}).get("text") or "{}")
        assert data.get("ok") is True
        groups = {g.get("prefix"): g for g in data.get("groups") or []}
        assert "pkg/" in groups and "other" in groups
        assert abs(float(groups["pkg/"]["threshold"]) - 0.95) < 1e-6
        assert abs(float(groups["other"]["threshold"]) - 0.90) < 1e-6


def test_mcp_ci_validate_and_autofix_backup(tmp_path: Path) -> None:
    with chdir(tmp_path):
        ensure_project_config()
        # Enable container + sast strict via compiled rules, and hadolint via config
        compiled = tmp_path / ".mcp/rules_compiled.json"
        compiled.parent.mkdir(parents=True, exist_ok=True)
        compiled.write_text(
            json.dumps({"policy": {"security.secrets_scan": True, "container.required": True, "security.sast_strict": True}}),
            encoding="utf-8",
        )
        cfg = tmp_path / ".mcp/assistant.yaml"
        y = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        y.setdefault("ci", {})["hadolint"] = True
        cfg.write_text(yaml.safe_dump(y, sort_keys=False, allow_unicode=True), encoding="utf-8")

        srv = JsonRpcServer()
        # First generate CI and validate steps
        g = srv.handle(_req("tools/call", {"name": "ci.generate"}))
        assert Path(g.get("result", {}).get("path") or "").exists()
        v = srv.handle(_req("tools/call", {"name": "ci.validate"}))
        checks = v.get("result", {}).get("checks", {})
        assert checks.get("exists") is True
        assert checks.get("has_precommit") is True
        assert checks.get("has_hadolint") is True
        assert checks.get("has_semgrep") is True
        assert checks.get("has_tests") is True
        assert checks.get("has_bandit") is True

        # Now perturb CI and auto-fix, expecting backup created and content restored
        ci_file = tmp_path / ".github/workflows/ci.yml"
        ci_file.write_text("name: stale\n", encoding="utf-8")
        af = srv.handle(_req("tools/call", {"name": "ci.autofix"}))
        assert af.get("result", {}).get("changed") is True
        backup = af.get("result", {}).get("backup") or ""
        assert backup and Path(backup).exists()

