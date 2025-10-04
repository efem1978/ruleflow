from __future__ import annotations

import json
import os
from pathlib import Path

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


def _req(method: str, params: dict | None = None, id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_initialize_and_tools_list(tmp_path: Path) -> None:
    with chdir(tmp_path):
        srv = JsonRpcServer()
        r1 = srv.handle(_req("initialize"))
        assert r1.get("result", {}).get("server") == "mcp-rules-assistant"
        r2 = srv.handle(_req("tools/list"))
        tools = [t.get("name") for t in r2.get("result", {}).get("tools", [])]
        assert (
            "config.get" in tools
            and "config.update" in tools
            and "rules.ingest" in tools
        )


def test_resources_plan_config_and_coverage(tmp_path: Path) -> None:
    with chdir(tmp_path):
        ensure_project_config()
        srv = JsonRpcServer()
        rlist = srv.handle(_req("resources/list"))
        uris = [r.get("uri") for r in rlist.get("result", {}).get("resources", [])]
        assert any(str(u).startswith("progress://") for u in uris)
        assert any(str(u).startswith("config://") for u in uris)
        # read config content (initially default or empty)
        cfg_uri = next(u for u in uris if str(u).startswith("config://"))
        rcfg = srv.handle(_req("resources/read", {"uri": cfg_uri}))
        assert rcfg.get("result", {}).get("mimeType") == "text/yaml"
        # coverage without file present returns ok False JSON
        cov_uri = next(
            u
            for u in uris
            if str(u).endswith("/summary") or str(u).startswith("coverage://")
        )
        rcov = srv.handle(_req("resources/read", {"uri": cov_uri}))
        data = json.loads(rcov.get("result", {}).get("text") or "{}")
        assert data.get("ok") in (True, False)


def test_rules_ingest_and_ci_validate(tmp_path: Path) -> None:
    with chdir(tmp_path):
        srv = JsonRpcServer()
        # prepare a rule doc
        d = tmp_path / "r.md"
        d.write_text("- 覆盖率 90%\n- 禁止 skip/xfail\n", encoding="utf-8")
        r = srv.handle(
            _req(
                "tools/call", {"name": "rules.ingest", "arguments": {"paths": [str(d)]}},
            ),
        )
        assert r.get("result", {}).get("files") == 1
        # generate and validate CI
        g = srv.handle(_req("tools/call", {"name": "ci.generate"}))
        assert Path(g.get("result", {}).get("path") or "").exists()
        v = srv.handle(_req("tools/call", {"name": "ci.validate"}))
        checks = v.get("result", {}).get("checks", {})
        assert (
            set(
                [
                    "exists",
                    "has_precommit",
                    "has_hadolint",
                    "has_semgrep",
                    "has_tests",
                    "has_bandit",
                ],
            )
            - set(checks.keys())
            == set()
        )
