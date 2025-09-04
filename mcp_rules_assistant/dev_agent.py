from __future__ import annotations

import argparse
import http.server
import json
import os
import socketserver
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Optional

from .coverage_summary import summarize, summarize_groups, summarize_near
from . import checks
from .progress import parse_plan, read_plan


def _run_tests_with_coverage(project_root: Path) -> Dict[str, object]:
    env = os.environ.copy()
    env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    cmd = [
        "pytest",
        "-q",
        "-p",
        "pytest_cov",
        "--maxfail=1",
        "--disable-warnings",
        "-W",
        "error",
        "--strict-markers",
        "--cov=mcp_rules_assistant",
        "--cov-report=xml:coverage.xml",
        "--cov-report=term-missing",
    ]
    try:
        p = subprocess.run(
            cmd,
            cwd=str(project_root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        return {
            "ok": p.returncode == 0,
            "code": p.returncode,
            "stdout": p.stdout[-8000:],
            "stderr": p.stderr[-8000:],
            "cmd": cmd,
        }
    except FileNotFoundError:
        return {"ok": False, "code": 127, "error": "pytest not found"}


def _git_changed_files(project_root: Path) -> list[Path]:
    try:
        p = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(project_root),
            text=True,
            stdout=subprocess.PIPE,
        )
        files: list[Path] = []
        for line in (p.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            # format: XY <path>
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                files.append(project_root / parts[1])
        return files
    except Exception:
        return []


def _run_impacted_or_full(project_root: Path, cycle_idx: int, full_every: int = 5) -> Dict[str, object]:
    # 周期性跑全量覆盖率，其他周期运行受影响测试（快速）
    try_quick = (cycle_idx % max(1, full_every)) != 0
    changed = _git_changed_files(project_root)
    if try_quick and changed:
        res = checks.run_quick_tests(changed, cwd=project_root)
        # 如果无受影响测试或 pytest 不可用，则退回全量
        if not res.get("skipped") and res.get("ok") in (True, False):
            res_copy = dict(res)
            res_copy["mode"] = "quick"
            return res_copy
    out = _run_tests_with_coverage(project_root)
    out["mode"] = "full"
    return out


def _ensure_dashboard_dir(root: Path) -> Path:
    d = root / ".mcp" / "dashboard"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_index_html(dashboard_dir: Path) -> None:
    index = (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>MCP Dev Board"\
        "</title><style>body{font-family:system-ui,Arial,sans-serif;padding:16px}"\
        " .ok{color:#2e7d32}.warn{color:#c62828}.card{border:1px solid #ddd;"\
        "border-radius:8px;padding:12px;margin:8px 0} code{background:#f6f8fa;"\
        "padding:2px 4px;border-radius:4px} .grid{display:grid;grid-template-columns:"\
        "repeat(auto-fill,minmax(320px,1fr));gap:12px} .mono{font-family:ui-monospace,Menlo,Consolas}"\
        "</style></head><body><h2>🚀 MCP Dev Dashboard</h2>"\
        "<div id=ts class=mono></div><div class=grid>"\
        "<div class=card><h3>Plan</h3><div id=plan></div></div>"\
        "<div class=card><h3>Tests</h3><pre id=tests class=mono></pre></div>"\
        "<div class=card><h3>Coverage Weak</h3><ul id=weak></ul></div>"\
        "<div class=card><h3>Coverage Near</h3><ul id=near></ul></div>"\
        "<div class=card><h3>Groups</h3><ul id=groups></ul></div>"\
        "</div><script>async function load(){const r=await fetch('status.json?'+Date.now());"\
        "const s=await r.json(); document.getElementById('ts').textContent="\
        "new Date(s.timestamp*1000).toLocaleString(); const p=s.plan||{};"\
        "document.getElementById('plan').innerHTML = '<div>Status: <b>'+(p.status||'')+"\
        "'</b></div><div>Current: <b>'+(p.current||'')+'</b></div><div>Next: '"\
        "+(p.next||'')+'</div>'; const t=s.tests||{}; const ok=t.ok?'ok':'warn';"\
        "document.getElementById('tests').textContent=(t.ok?'✔':'✘')+' code='+t.code+"\
        "'\n'+(t.stdout||'').slice(-1000); const w=s.coverage&&s.coverage.weak||[];"\
        "document.getElementById('weak').innerHTML=w.slice(0,20).map(x=>'<li>'+(x.coverage*100).toFixed(1)+'% &lt; '+Math.round((x.threshold||0)*100)+'% — '+x.file+'</li>').join('');"\
        "const n=s.coverage&&s.coverage.near||[]; document.getElementById('near').innerHTML=n.slice(0,20).map(x=>'<li>'+(x.coverage*100).toFixed(1)+'% ≥ '+Math.round((x.threshold||0)*100)+'% — '+x.file+'（Δ+'+((x.delta_up||0)*100).toFixed(1)+'%）</li>').join('');"\
        "const g=s.coverage&&s.coverage.groups||[]; document.getElementById('groups').innerHTML=g.map(x=>'<li>'+x.prefix+': '+(x.coverage*100).toFixed(1)+'% &lt; '+Math.round((x.threshold||0)*100)+'% — 弱项 '+x.weak_count+'/'+x.files_count+'</li>').join(''); } load(); setInterval(load, 5000);</script>"\
        "</body></html>"
    )
    (dashboard_dir / "index.html").write_text(index, encoding="utf-8")


def compute_status(project_root: Path) -> Dict[str, object]:
    # ensure plan
    try:
        plan_text = read_plan(project_root)
        status, current, nxt = parse_plan(plan_text)
        plan_obj = {"status": status, "current": current, "next": nxt}
    except Exception:
        plan_obj = {"status": "", "current": "", "next": ""}

    # coverage summaries (require coverage.xml)
    cov_summary = summarize(project_root=project_root)
    cov_groups = summarize_groups(project_root=project_root)
    cov_near = summarize_near(project_root=project_root)
    weak = cov_summary.get("weak", []) if isinstance(cov_summary, dict) else []
    groups = cov_groups.get("groups", []) if isinstance(cov_groups, dict) else []
    near = cov_near.get("near", []) if isinstance(cov_near, dict) else []
    min_module = (
        float(cov_summary.get("min_module", 0.9)) if isinstance(cov_summary, dict) else 0.9
    )
    return {
        "plan": plan_obj,
        "coverage": {
            "weak": weak,
            "groups": groups,
            "near": near,
            "min_module": min_module,
        },
    }


def serve_directory(directory: Path, bind: str) -> socketserver.TCPServer:
    os.chdir(str(directory))
    host, port_str = bind.split(":") if ":" in bind else (bind, "8080")
    port = int(port_str)
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer((host, port), handler)
    return httpd


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser("dev-agent")
    ap.add_argument("--interval", type=int, default=60, help="run interval seconds")
    ap.add_argument(
        "--serve",
        type=str,
        default="",
        help="bind host:port to serve dashboard (e.g., 0.0.0.0:8080)",
    )
    args = ap.parse_args(argv)

    root = Path.cwd().resolve()
    dash = _ensure_dashboard_dir(root)
    _write_index_html(dash)

    httpd: Optional[socketserver.TCPServer] = None
    if args.serve:
        httpd = serve_directory(dash, args.serve)
        th = threading.Thread(target=httpd.serve_forever, daemon=True)
        th.start()

    # auto-commit/push 配置
    auto_commit = os.environ.get("DEV_AGENT_AUTOCOMMIT", "0") in ("1", "true", "True")
    auto_push = os.environ.get("DEV_AGENT_AUTOPUSH", "0") in ("1", "true", "True")
    commit_interval = int(os.environ.get("DEV_AGENT_COMMIT_INTERVAL", "600"))
    last_commit_ts = 0.0

    cycle = 0
    while True:
        t0 = time.time()
        tests = _run_impacted_or_full(root, cycle_idx=cycle, full_every=5)
        status = {
            "timestamp": time.time(),
            "tests": tests,
        }
        try:
            status.update(compute_status(root))
        except Exception as e:
            status["error"] = f"status compute failed: {e}"
        (dash / "status.json").write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")

        # 可选：定时自动提交（需计划处于 in_progress 且 current 存在）
        if auto_commit and (time.time() - last_commit_ts) >= commit_interval:
            try:
                plan_text = read_plan(root)
                st, cur, _ = parse_plan(plan_text)
                if st == "in_progress" and cur:
                    # 若有变更则提交
                    proc = subprocess.run(["git", "status", "--porcelain"], cwd=str(root), text=True, stdout=subprocess.PIPE)
                    if (proc.stdout or "").strip():
                        subprocess.run(["git", "add", "-A"], cwd=str(root), check=False)
                        msg = f"chore(agent): auto update [step:{cur}]"
                        subprocess.run(["git", "commit", "-m", msg], cwd=str(root), check=False)
                        if auto_push:
                            subprocess.run(["git", "push"], cwd=str(root), check=False)
                        last_commit_ts = time.time()
            except Exception:
                pass

        dt = max(1, args.interval - int(time.time() - t0))
        time.sleep(dt)
        cycle += 1


if __name__ == "__main__":
    main()
