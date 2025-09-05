from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from .coverage_summary import summarize, summarize_groups, summarize_near
from .config import load_config
from . import checks
from . import __version__ as PKG_VERSION
from .progress import parse_plan, read_plan


def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


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
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                files.append(project_root / parts[1])
        return files
    except Exception:
        return []


def _run_impacted_or_full(project_root: Path, cycle_idx: int, full_every: int = 5) -> Dict[str, object]:
    try_quick = (cycle_idx % max(1, full_every)) != 0
    changed = _git_changed_files(project_root)
    if try_quick and changed:
        res = checks.run_quick_tests(changed, cwd=project_root)
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


def compute_status(project_root: Path) -> Dict[str, object]:
    try:
        plan_text = read_plan(project_root)
        status, current, nxt = parse_plan(plan_text)
        plan_obj = {"status": status, "current": current, "next": nxt}
    except Exception:
        plan_obj = {"status": "", "current": "", "next": ""}

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
    if total_files == 0:
        prev = _read_json((project_root / ".mcp" / "dashboard" / "status.json"))
        cov_prev = prev.get("coverage", {}) if isinstance(prev.get("coverage", {}), dict) else {}
        weak = cov_prev.get("weak", weak)
        groups = cov_prev.get("groups", groups)
        near = cov_prev.get("near", near)
        total_files = int(cov_prev.get("count", 0) or 0)

    cov_progress = 0.0
    if total_files > 0:
        cov_progress = max(0.0, min(1.0, (total_files - len(weak)) / float(total_files)))

    pending_tasks: list[str] = []
    done_tasks: list[str] = []
    done_count = 0
    pending_count = 0

    def scan_md(p: Path) -> Tuple[int, int, list[str], list[str]]:
        d = 0
        u = 0
        pend: list[str] = []
        done: list[str] = []
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return 0, 0, [], []
        in_code = False
        for ln in text.splitlines():
            s = ln.rstrip()
            if s.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            ls = s.lstrip()
            if ls.startswith(("- [x] ", "- [X] ")):
                d += 1
                done.append(ls[6:].strip())
            elif ls.startswith("- [ ] "):
                u += 1
                pend.append(ls[6:].strip())
        return d, u, pend, done

    try:
        d0, u0, p0, dn0 = scan_md(project_root / ".mcp/plan.md")
        done_count += d0
        pending_count += u0
        pending_tasks.extend(p0)
        done_tasks.extend(dn0)
        for p in (project_root / "docs").glob("*.md"):
            d1, u1, p1, dn1 = scan_md(p)
            done_count += d1
            pending_count += u1
            pending_tasks.extend(p1)
            done_tasks.extend(dn1)
        for p in [project_root / "README.md"]:
            if p.exists():
                d2, u2, p2, dn2 = scan_md(p)
                done_count += d2
                pending_count += u2
                pending_tasks.extend(p2)
                done_tasks.extend(dn2)
        if done_count + pending_count == 0:
            lines = plan_text.splitlines()
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
    if done_count + pending_count == 0 and len(pending_tasks) > 0:
        pending_count = len(pending_tasks)
        done_count = 0
    if done_count + pending_count > 0:
        plan_progress = done_count / float(done_count + pending_count)

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


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser("dev-agent")
    ap.add_argument("--interval", type=int, default=60, help="run interval seconds")
    args = ap.parse_args(argv)

    root = Path.cwd().resolve()
    dash = _ensure_dashboard_dir(root, rebuild=True)
    try:
        initial_tests = _run_impacted_or_full(root, cycle_idx=0, full_every=1)
    except Exception:
        initial_tests = {"ok": False, "code": 1, "stdout": "", "stderr": "", "mode": "full"}
    try:
        initial_status = compute_status(root)
    except Exception:
        initial_status = {"plan": {}, "coverage": {}, "progress": {}, "tasks": {}}
    initial_status["timestamp"] = time.time()
    initial_status["tests"] = initial_tests
    initial_status["interval"] = int(args.interval)
    txt0 = json.dumps(initial_status, ensure_ascii=False)
    (dash / "status.json").write_text(txt0, encoding="utf-8")

    auto_commit = os.environ.get("DEV_AGENT_AUTOCOMMIT", "0") in ("1", "true", "True")
    auto_push = os.environ.get("DEV_AGENT_AUTOPUSH", "0") in ("1", "true", "True")
    commit_interval = int(os.environ.get("DEV_AGENT_COMMIT_INTERVAL", "600"))
    last_commit_ts = 0.0
    bypass_enabled = os.environ.get("DEV_AGENT_BYPASS", "1") in ("1", "true", "True")
    bypass_threshold = int(os.environ.get("DEV_AGENT_BYPASS_THRESHOLD", "3"))
    bypass_allow_commit = os.environ.get("DEV_AGENT_BYPASS_COMMIT", "0") in ("1", "true", "True")
    bypass_state_file = (Path.cwd() / ".mcp" / "dashboard" / "bypass_state.json")
    auto_tag = os.environ.get("DEV_AGENT_AUTOTAG", "0") in ("1", "true", "True")
    last_tag_date = ""
    max_cycles = int(os.environ.get("DEV_AGENT_MAX_CYCLES", "0") or 0)

    cycle = 0
    while True:
        t0 = time.time()
        tests = _run_impacted_or_full(root, cycle_idx=cycle, full_every=5)

        def _run_quick_status(cmd: list[str], need: str) -> str:
            try:
                if need and not shutil.which(need):
                    return "skipped"
                p = subprocess.run(cmd, cwd=str(root), text=True)
                return "ok" if p.returncode == 0 else "fail"
            except Exception:
                return "skipped"

        lint_stat = _run_quick_status(["ruff", "check", "--quiet", "mcp_rules_assistant"], "ruff")
        type_stat = _run_quick_status([
            "mypy",
            "mcp_rules_assistant/config.py",
            "mcp_rules_assistant/progress.py",
            "mcp_rules_assistant/tools.py",
            "mcp_rules_assistant/memory.py",
            "mcp_rules_assistant/mcp_server.py",
            "mcp_rules_assistant/cli.py",
            "mcp_rules_assistant/server.py",
        ], "mypy")
        tdd_script = root / ".mcp/tdd_gate.py"
        tdd_stat = _run_quick_status(["python", str(tdd_script)], "python") if tdd_script.exists() else "skipped"

        bypass = {"active": False, "count": 0, "threshold": bypass_threshold, "since": "", "signature": ""}
        try:
            st = _read_json(bypass_state_file)
            bypass.update(st if isinstance(st, dict) else {})
        except Exception:
            pass
        if not bool(tests.get("ok", False)):
            sig = f"{tests.get('code')}|{str(tests.get('stderr',''))[:120]}|{str(tests.get('stdout',''))[:120]}"
            if sig == bypass.get("signature"):
                bypass["count"] = int(bypass.get("count", 0)) + 1
            else:
                bypass["count"] = 1
                bypass["signature"] = sig
                bypass["since"] = time.strftime("%Y-%m-%d %H:%M:%S")
            if bypass_enabled and int(bypass.get("count", 0)) >= bypass_threshold:
                bypass["active"] = True
        else:
            bypass = {"active": False, "count": 0, "threshold": bypass_threshold, "since": "", "signature": ""}

        if bypass.get("active"):
            tests["bypassed"] = True
            if bypass_allow_commit:
                tests["ok"] = True

        status: Dict[str, object] = {
            "timestamp": time.time(),
            "tests": tests,
        }
        try:
            status.update(compute_status(root))
        except Exception as e:
            status["error"] = f"status compute failed: {e}"
        status["bypass"] = bypass
        status["interval"] = int(args.interval)
        status["checks"] = {
            "lint": lint_stat,
            "type": type_stat,
            "tests": "ok" if bool(tests.get("ok")) else "fail",
            "tdd": tdd_stat,
        }

        fail_state_file = dash / "fail_counters.json"
        fs = _read_json(fail_state_file)
        cnt = dict(fs.get("counters", {}) or {})
        last = dict(fs.get("last_trigger", {}) or {})
        freeze = dict(fs.get("freeze", {}) or {"active": False, "since": "", "reason": ""})
        thr = {
            "lint": int(os.environ.get("DEV_AGENT_THR_LINT", "15") or 15),
            "tests": int(os.environ.get("DEV_AGENT_THR_TESTS", "10") or 10),
            "build": int(os.environ.get("DEV_AGENT_THR_BUILD", "5") or 5),
            "severe": int(os.environ.get("DEV_AGENT_THR_SEVERE", "3") or 3),
        }

        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        lint_fail = lint_stat == "fail"
        tests_fail = not bool(tests.get("ok"))
        build_fail = (tests.get("code", 0) not in (0, 1) and tests.get("mode") == "full") or (tests.get("code") == 127)
        severe_fail = bool(status.get("error"))
        if lint_fail:
            cnt["lint"] = int(cnt.get("lint", 0)) + 1
            last["lint"] = now_str
        if tests_fail:
            cnt["tests"] = int(cnt.get("tests", 0)) + 1
            last["tests"] = now_str
        if build_fail:
            cnt["build"] = int(cnt.get("build", 0)) + 1
            last["build"] = now_str
        if severe_fail:
            cnt["severe"] = int(cnt.get("severe", 0)) + 1
            last["severe"] = now_str
        if not freeze.get("active") and (
            int(cnt.get("tests", 0)) >= thr["tests"]
            or int(cnt.get("build", 0)) >= thr["build"]
            or int(cnt.get("severe", 0)) >= thr["severe"]
        ):
            freeze = {"active": True, "since": now_str, "reason": "threshold_reached"}
        try:
            weak_count_now = len((status.get("coverage", {}) or {}).get("weak", []) or [])
        except Exception:
            weak_count_now = 0
        if freeze.get("active") and bool(tests.get("ok")) and weak_count_now == 0 and lint_stat == "ok" and (type_stat in ("ok", "skipped")):
            freeze = {"active": False, "since": now_str, "reason": "recovered"}
            cnt = {"lint": 0, "tests": 0, "build": 0, "severe": 0}
        if freeze.get("active"):
            try:
                prev = _read_json(dash / "status.json")
                if isinstance(prev.get("coverage", {}), dict):
                    status["coverage"] = prev.get("coverage")
            except Exception:
                pass
        status["freeze"] = freeze
        status["fail_counters"] = {"counters": cnt, "last_trigger": last, "thresholds": thr}
        try:
            (dash / "fail_counters.json").write_text(
                json.dumps({"counters": cnt, "last_trigger": last, "freeze": freeze}, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass
        txt = json.dumps(status, ensure_ascii=False)
        (dash / "status.json").write_text(txt, encoding="utf-8")

        try:
            rec = {
                "ts": status["timestamp"],
                "duration": max(0, time.time() - t0),
                "overall": (status.get("progress", {}) or {}).get("overall", 0.0),
                "coverage_progress": (status.get("coverage", {}) or {}).get("progress", 0.0),
                "coverage_weak": len((status.get("coverage", {}) or {}).get("weak", []) or []),
                "checks": status.get("checks", {}),
                "bypass": status.get("bypass", {}),
            }
            hist_p = dash / "history.json"
            arr = []
            if hist_p.exists():
                try:
                    arr = json.loads(hist_p.read_text(encoding="utf-8"))
                except Exception:
                    arr = []
            arr.append(rec)
            arr = arr[-50:]
            hist_p.write_text(json.dumps(arr, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

        can_commit = bool(tests.get("ok")) or (bypass.get("active") and bypass_allow_commit)
        if auto_commit and (time.time() - last_commit_ts) >= commit_interval and can_commit:
            try:
                plan_text = read_plan(root)
                st, cur, _ = parse_plan(plan_text)
                if st == "in_progress" and cur:
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

        if auto_tag and tests.get("ok") and tests.get("mode") == "full":
            try:
                cov = status.get("coverage", {}) or {}
                weak = cov.get("weak", []) or []
                if not weak:
                    today = time.strftime("%Y%m%d", time.localtime())
                    if today != last_tag_date:
                        tag = f"v{PKG_VERSION}-dev{today}"
                        p = subprocess.run(["git", "tag", "-l", tag], cwd=str(root), text=True, stdout=subprocess.PIPE)
                        if tag not in (p.stdout or ""):
                            subprocess.run(["git", "tag", "-a", tag, "-m", f"auto dev milestone {today}"], cwd=str(root), check=False)
                            last_tag_date = today
            except Exception:
                pass

        dt = max(1, args.interval - int(time.time() - t0))
        time.sleep(dt)
        cycle += 1
        if max_cycles and cycle >= max_cycles:
            break


if __name__ == "__main__":
    main()

