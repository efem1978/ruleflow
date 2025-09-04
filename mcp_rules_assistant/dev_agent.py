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
import shutil
from typing import Dict, Optional

from .coverage_summary import summarize, summarize_groups, summarize_near
from .config import load_config
from . import checks
from . import __version__ as PKG_VERSION
from .progress import parse_plan, read_plan


def _run_tests_with_coverage(project_root: Path) -> Dict[str, object]:
    env = os.environ.copy()
    env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    py = os.environ.get("PYTHON_BIN") or "python3"
    cmd = [
        py,
        "-m",
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
        return {"ok": False, "code": 127, "error": "python/pytest not found"}


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


def _ensure_dashboard_dir(root: Path, rebuild: bool = False) -> Path:
    d = root / ".mcp" / "dashboard"
    if rebuild and d.exists():
        try:
            shutil.rmtree(d)
        except Exception:
            pass
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_index_html(dashboard_dir: Path, embed_status: Optional[Dict[str, object]] = None) -> None:
    index = (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>MCP Dev Board"\
        "</title><style>body{font-family:system-ui,Arial,sans-serif;padding:16px}"\
        " .ok{color:#2e7d32}.warn{color:#c62828}.card{border:1px solid #ddd;"\
        "border-radius:8px;padding:12px;margin:8px 0} code{background:#f6f8fa;"\
        "padding:2px 4px;border-radius:4px} .grid{display:grid;grid-template-columns:"\
        "repeat(auto-fill,minmax(320px,1fr));gap:12px} .mono{font-family:ui-monospace,Menlo,Consolas}"\
        ".bar{height:10px;background:#eee;border-radius:5px;overflow:hidden}"\
        ".bar>span{display:block;height:10px;background:#4caf50}"\
        "</style></head><body><h2>🚀 MCP Dev Dashboard</h2>"\
        "<div id=ts class=mono></div><div class=grid>"\
        "<div class=card><h3>Progress</h3><div>Overall: <b><span id=ovp>—</span>%</b></div>"\
        "<div class=bar><span id=ovbar style='width:0%'></span></div>"\
        "<div>Coverage: <span id=cvp>—</span>% (<span id=cvok>0</span>/<span id=cvtotal>0</span>)</div>"\
        "<div>Plan (Doc): <span id=plp>—</span>% (<span id=pld>0</span> done, <span id=plpnd>0</span> pending)</div>"\
        "<div>Prod: <span id=prp>—</span>%</div></div>"\
        "<div class=card><h3>Plan</h3><div id=plan></div></div>"\
        "<div class=card><h3>Tests</h3><pre id=tests class=mono></pre></div>"\
        "<div class=card><h3>Coverage Weak</h3><ul id=weak></ul></div>"\
        "<div class=card><h3>Coverage Near</h3><ul id=near></ul></div>"\
        "<div class=card><h3>Groups</h3><ul id=groups></ul></div>"\
        "<div class=card><h3>Next Tasks</h3><ol id=pending></ol></div>"\
        "</div>"\
        + ("<script>window.__status = "
           + json.dumps(embed_status, ensure_ascii=False)
           + ";</script>" if embed_status else "") \
        + "<script>async function load(){try{const r=await fetch('/status.json?'+Date.now());"\
        "const s=await r.json(); document.getElementById('ts').textContent="\
        "new Date(s.timestamp*1000).toLocaleString(); const p=s.plan||{};"\
        "document.getElementById('plan').innerHTML = '<div>Status: <b>'+(p.status||'')+"\
        "'</b></div><div>Current: <b>'+(p.current||'')+'</b></div><div>Next: '"\
        "+(p.next||'')+'</div>'; const t=s.tests||{}; const ok=t.ok?'ok':'warn';"\
        "document.getElementById('tests').textContent=(t.ok?'✔':'✘')+' code='+t.code+"\
        "'\n'+(t.stdout||'').slice(-1000); const w=s.coverage&&s.coverage.weak||[];"\
        "document.getElementById('weak').innerHTML=w.slice(0,20).map(x=>'<li>'+(x.coverage*100).toFixed(1)+'% &lt; '+Math.round((x.threshold||0)*100)+'% — '+x.file+'</li>').join('');"\
        "const n=s.coverage&&s.coverage.near||[]; document.getElementById('near').innerHTML=n.slice(0,20).map(x=>'<li>'+(x.coverage*100).toFixed(1)+'% ≥ '+Math.round((x.threshold||0)*100)+'% — '+x.file+'（Δ+'+((x.delta_up||0)*100).toFixed(1)+'%）</li>').join('');"\
        "const g=s.coverage&&s.coverage.groups||[]; document.getElementById('groups').innerHTML=g.map(x=>'<li>'+x.prefix+': '+(x.coverage*100).toFixed(1)+'% &lt; '+Math.round((x.threshold||0)*100)+'% — 弱项 '+x.weak_count+'/'+x.files_count+'</li>').join('');"\
        "const prog=s.progress||{}; const cov=s.coverage||{}; const overall=((prog.overall||0)*100).toFixed(0);"\
        "document.getElementById('ovp').textContent=overall; document.getElementById('ovbar').style.width=overall+'%';"\
        "document.getElementById('cvp').textContent=((cov.progress||0)*100).toFixed(0);"\
        "document.getElementById('cvok').textContent=(cov.count||0)-( (cov.weak||[]).length ||0 );"\
        "document.getElementById('cvtotal').textContent=(cov.count||0);"\
        "const pc=prog.counts||{}; const plp=prog.plan==null?'—':(prog.plan*100).toFixed(0);"\
        "document.getElementById('plp').textContent=plp; document.getElementById('pld').textContent=(pc.plan_done||0); document.getElementById('plpnd').textContent=(pc.plan_pending||0);"\
        "document.getElementById('prp').textContent=((prog.prod||0)*100).toFixed(0);"\
        "const pend=(s.tasks&&s.tasks.pending)||[]; document.getElementById('pending').innerHTML=pend.map(x=>'<li>'+x+'</li>').join('');}catch(e){console.warn('[dashboard] fetch /status.json failed, trying embedded'); try{const s=window.__status; if(s){document.getElementById('ts').textContent=new Date(s.timestamp*1000).toLocaleString(); const p=s.plan||{};document.getElementById('plan').innerHTML = '<div>Status: <b>'+(p.status||'')+'</b></div><div>Current: <b>'+(p.current||'')+'</b></div><div>Next: '+(p.next||'')+'</div>'; const t=s.tests||{};document.getElementById('tests').textContent=(t.ok?'✔':'✘')+' code='+(t.code||'')+'\n'+((t.stdout||'').slice(-1000)||''); const w=(s.coverage&&s.coverage.weak)||[];document.getElementById('weak').innerHTML=w.slice(0,20).map(x=>'<li>'+(x.coverage*100).toFixed(1)+'% &lt; '+Math.round((x.threshold||0)*100)+'% — '+x.file+'</li>').join(''); const n=(s.coverage&&s.coverage.near)||[]; document.getElementById('near').innerHTML=n.slice(0,20).map(x=>'<li>'+(x.coverage*100).toFixed(1)+'% ≥ '+Math.round((x.threshold||0)*100)+'% — '+x.file+'（Δ+'+((x.delta_up||0)*100).toFixed(1)+'%）</li>').join(''); const g=(s.coverage&&s.coverage.groups)||[]; document.getElementById('groups').innerHTML=g.map(x=>'<li>'+x.prefix+': '+(x.coverage*100).toFixed(1)+'% &lt; '+Math.round((x.threshold||0)*100)+'% — 弱项 '+x.weak_count+'/'+x.files_count+'</li>').join(''); const prog=s.progress||{}; const cov=s.coverage||{}; const overall=((prog.overall||0)*100).toFixed(0); document.getElementById('ovp').textContent=overall; document.getElementById('ovbar').style.width=overall+'%'; document.getElementById('cvp').textContent=((cov.progress||0)*100).toFixed(0); document.getElementById('cvok').textContent=(cov.count||0)-(((cov.weak||[]).length)||0); document.getElementById('cvtotal').textContent=(cov.count||0); const pc=prog.counts||{}; const plp=prog.plan==null?'—':(prog.plan*100).toFixed(0); document.getElementById('plp').textContent=plp; document.getElementById('pld').textContent=(pc.plan_done||0); document.getElementById('plpnd').textContent=(pc.plan_pending||0); document.getElementById('prp').textContent=((prog.prod||0)*100).toFixed(0); const pend=(s.tasks&&s.tasks.pending)||[]; document.getElementById('pending').innerHTML=pend.map(x=>'<li>'+x+'</li>').join('');} else {document.getElementById('tests').textContent='[dashboard] status unavailable';}}catch(e2){console.error(e2); document.getElementById('tests').textContent='[dashboard] load error: '+e2;}}} load(); setInterval(load, 5000);</script>"\
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

    # coverage summaries (require coverage.xml) — honor project config thresholds
    try:
        cfg = load_config(project_root)
    except Exception:
        cfg = {}
    perf = cfg.get("performance", {}) if isinstance(cfg.get("performance", {}), dict) else {}
    min_module = float(((perf.get("on_push", {}) or {}).get("coverage", {}) or {}).get("min_module", 0.9))
    policy = (cfg.get("coverage", {}) or {}).get("policy", None) if isinstance(cfg.get("coverage", {}), dict) else None
    cov_summary = summarize(project_root=project_root, policy=policy, min_module=min_module)
    cov_groups = summarize_groups(project_root=project_root, policy=policy, min_module=min_module)
    cov_near = summarize_near(project_root=project_root, policy=policy, min_module=min_module)
    weak = cov_summary.get("weak", []) if isinstance(cov_summary, dict) else []
    groups = cov_groups.get("groups", []) if isinstance(cov_groups, dict) else []
    near = cov_near.get("near", []) if isinstance(cov_near, dict) else []
    total_files = int(cov_summary.get("count", 0)) if isinstance(cov_summary, dict) else 0
    # min_module 已按配置读取

    # 计算覆盖率进度：满足阈值的文件比例（若无数据则为 0）
    cov_progress = 0.0
    if total_files > 0:
        cov_progress = max(0.0, min(1.0, (total_files - len(weak)) / float(total_files)))

    # 解析计划中的任务（支持 markdown checkbox）
    pending_tasks: list[str] = []
    done_tasks: list[str] = []
    done_count = 0
    pending_count = 0
    try:
        lines = plan_text.splitlines()
        for ln in lines:
            s = ln.strip()
            if s.startswith(('- [x] ', '- [X] ')):
                done_count += 1
                done_tasks.append(s[6:].strip())
            elif s.startswith('- [ ] '):
                pending_count += 1
                pending_tasks.append(s[6:].strip())
        # 若未使用 checkbox，尝试从“待办/Next/下一步/待办聚焦”后收集一级列表项
        if done_count + pending_count == 0:
            capture = False
            for ln in lines:
                raw = ln.rstrip()
                low = raw.lower()
                if any(k in low for k in ['待办', 'next actions', '下一步']):
                    capture = True
                    continue
                if capture:
                    if raw.strip().startswith('- '):
                        item = raw.strip()[2:].strip()
                        if item:
                            pending_tasks.append(item)
                    elif raw.strip() == '' or raw.startswith('#'):
                        break
            if pending_tasks:
                pending_count = len(pending_tasks)
                done_count = 0
    except Exception:
        pass

    plan_progress = None
    if done_count + pending_count > 0:
        plan_progress = done_count / float(done_count + pending_count)

    # 生产级就绪度（粗略）：关键工件存在性 + 覆盖率 Gate
    prod_checks = {
        "coverage_gate": len(weak) == 0,
        "precommit_config": (project_root / ".pre-commit-config.yaml").exists(),
        "pre_push_hook": (project_root / ".git/hooks/pre-push").exists(),
        "plan_gate": (project_root / ".mcp/plan_gate.py").exists(),
        "branch_gate": (project_root / ".mcp/branch_name_gate.py").exists(),
        "ci_workflow": (project_root / ".github/workflows/ci.yml").exists(),
        "dockerfile": (project_root / "Dockerfile").exists(),
        "devcontainer": (project_root / ".devcontainer/devcontainer.json").exists(),
    }
    prod_progress = sum(1 for v in prod_checks.values() if v) / float(len(prod_checks)) if prod_checks else 0.0

    # 总进度：覆盖率权重 60%，计划权重 40%（若无计划数据则仅用覆盖率）
    overall = cov_progress
    if plan_progress is not None:
        overall = 0.6 * cov_progress + 0.4 * float(plan_progress)
    return {
        "plan": plan_obj,
        "coverage": {
            "weak": weak,
            "groups": groups,
            "near": near,
            "min_module": min_module,
            "count": total_files,
            "progress": cov_progress,
        },
        "progress": {
            "overall": overall,
            "coverage": cov_progress,
            "plan": plan_progress if plan_progress is not None else None,
            "doc": plan_progress if plan_progress is not None else None,
            "prod": prod_progress,
            "counts": {
                "coverage_total": total_files,
                "coverage_weak": len(weak),
                "plan_done": done_count,
                "plan_pending": pending_count,
            },
            "prod_checks": prod_checks,
        },
        "tasks": {
            "pending": pending_tasks[:20],
            "done": done_tasks[:20],
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
    auto_tag = os.environ.get("DEV_AGENT_AUTOTAG", "0") in ("1", "true", "True")
    last_tag_date = ""

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
        # 作为 file:// 直接打开时的回退（不依赖 fetch）
        (dash / "status.js").write_text("window.__status = " + json.dumps(status, ensure_ascii=False) + ";", encoding="utf-8")

        # 可选：定时自动提交（需计划处于 in_progress 且 current 存在）
        if auto_commit and (time.time() - last_commit_ts) >= commit_interval and bool(tests.get("ok")):
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

        # 可选：每日里程碑自动 tag（仅在全量测试通过且覆盖率 Gate 通过时；不推送）
        if auto_tag and tests.get("ok") and tests.get("mode") == "full":
            try:
                cov = status.get("coverage", {}) or {}
                weak = cov.get("weak", []) or []
                if not weak:
                    today = time.strftime("%Y%m%d", time.localtime())
                    if today != last_tag_date:
                        tag = f"v{PKG_VERSION}-dev{today}"
                        # 若 tag 不存在则创建
                        p = subprocess.run(["git", "tag", "-l", tag], cwd=str(root), text=True, stdout=subprocess.PIPE)
                        if tag not in (p.stdout or ""):
                            subprocess.run(["git", "tag", "-a", tag, "-m", f"auto dev milestone {today}"], cwd=str(root), check=False)
                            last_tag_date = today
            except Exception:
                pass

        dt = max(1, args.interval - int(time.time() - t0))
        time.sleep(dt)
        cycle += 1


if __name__ == "__main__":
    main()
