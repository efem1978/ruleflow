#!/usr/bin/env python3
"""
Spawn the MCP server (stdio), send a few JSON-RPC requests, and print a compact summary.
This is a non-interactive smoke test to verify "loaded and responding" state.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def venv_python() -> str:
    root = Path.cwd()
    if os.name == "nt":
        p = root / ".mcp/venv/Scripts/python.exe"
    else:
        p = root / ".mcp/venv/bin/python"
    return str(p if p.exists() else sys.executable)


def main() -> int:
    py = venv_python()
    # Start server
    proc = subprocess.Popen(
        [py, "-m", "mcp_rules_assistant.cli", "start"],
        cwd=str(Path.cwd()),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    def rpc(req_id: int, method: str, params: dict | None = None, timeout: float = 5.0):
        line = json.dumps(
            {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
        )
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(line + "\n")
        proc.stdin.flush()
        # read lines until id matches
        t0 = time.time()
        while time.time() - t0 < timeout:
            rl = proc.stdout.readline()
            if not rl:
                time.sleep(0.05)
                continue
            try:
                msg = json.loads(rl)
            except Exception:
                continue
            if msg.get("id") == req_id:
                return msg.get("result") or msg.get("error")
        raise RuntimeError(f"timeout waiting response for id={req_id}")

    try:
        init = rpc(1, "initialize")
        tools = rpc(2, "tools/list")
        res_list = rpc(3, "resources/list")
        # find plan uri and coverage report uri
        plan_uri = None
        cov_uri = None
        for it in res_list.get("resources") or []:
            u = str(it.get("uri", ""))
            if u.startswith("progress://") and u.endswith("/plan"):
                plan_uri = u
            if u.startswith("coverage://") and u.endswith("/report"):
                cov_uri = u
        plan = (
            rpc(4, "resources/read", {"uri": plan_uri})
            if plan_uri
            else {"mimeType": "", "text": ""}
        )
        cov = (
            rpc(5, "resources/read", {"uri": cov_uri})
            if cov_uri
            else {"mimeType": "", "text": ""}
        )
        # summarize
        tools_n = len(tools.get("tools") or [])
        cov_ok = False
        try:
            cov_json = json.loads(cov.get("text", "{}"))
            cov_ok = bool(cov_json.get("ok", False))
        except Exception:
            cov_ok = False
        print(
            json.dumps(
                {
                    "server": init.get("server"),
                    "version": init.get("version"),
                    "tools": tools_n,
                    "plan_mime": plan.get("mimeType"),
                    "coverage_ok": cov_ok,
                },
                ensure_ascii=False,
            )
        )
    finally:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except Exception:
                proc.kill()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
