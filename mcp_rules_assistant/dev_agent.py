from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict, cast

from . import __version__ as PKG_VERSION
from . import checks
from .atomics import atomic_write_text
from .config import get_coverage_policy, get_min_module, load_config
from .coverage_summary import summarize, summarize_groups, summarize_near
from .process import run_cmd as run_cmd
from .progress import parse_plan, read_plan

# Avoid magic strings for common paths/files
MCP_DIR_NAME = ".mcp"
DASHBOARD_SUBDIR = "dashboard"
STATUS_FILE = "status.json"
FAIL_COUNTERS_FILE = "fail_counters.json"
HISTORY_FILE = "history.json"


class Steps(str, Enum):
    LINT = "lint"
    TYPE = "type"
    TESTS = "tests"
    TDD = "tdd"


# Step name constants (compat): keep string values stable
STEP_LINT = Steps.LINT.value
STEP_TYPE = Steps.TYPE.value
STEP_TESTS = Steps.TESTS.value
STEP_TDD = Steps.TDD.value


class BypassState(TypedDict, total=False):
    active: bool
    count: int
    threshold: int
    since: str
    signature: str


class FreezeState(TypedDict, total=False):
    active: bool
    since: str
    reason: str


class FailCounters(TypedDict, total=False):
    lint: int
    tests: int
    build: int
    severe: int


class LastTrigger(TypedDict, total=False):
    lint: str
    tests: str
    build: str
    severe: str


class DevAgent:
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd().resolve()
        self.config = load_config(self.project_root)

    def _read_json(self, p: Path) -> Dict[str, Any]:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _run_tests_with_coverage(
        self, *, on_event: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, object]:
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
            try:
                p = run_cmd(
                    cmd,
                    cwd=self.project_root,
                    capture_stdout=True,
                    env=env,
                    on_event=on_event,
                )
            except TypeError:
                p = run_cmd(
                    cmd,
                    cwd=self.project_root,
                    capture_stdout=True,
                    env=env,
                )
            return {
                "ok": p.returncode == 0,
                "code": p.returncode,
                "stdout": (p.stdout or "")[-8000:],
                "stderr": (p.stderr or "")[-8000:],
                "cmd": cmd,
            }
        except FileNotFoundError:
            return {"ok": False, "code": 127, "error": "python/pytest not found"}

    def _git_changed_files(
        self, *, on_event: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> list[Path]:
        try:
            try:
                p = run_cmd(
                    ["git", "status", "--porcelain"],
                    cwd=self.project_root,
                    capture_stdout=True,
                    on_event=on_event,
                )
            except TypeError:
                p = run_cmd(
                    ["git", "status", "--porcelain"],
                    cwd=self.project_root,
                    capture_stdout=True,
                )
            files: list[Path] = []
            for line in (p.stdout or "").splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    files.append(self.project_root / parts[1])
            return files
        except Exception:
            return []

    def _run_impacted_or_full(
        self,
        cycle_idx: int,
        full_every: int = 5,
        *,
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, object]:
        # If tests monkeypatched module-level helper, delegate to it; otherwise use
        # instance-level logic so agent-level monkeypatches (_git_changed_files, etc.) work.
        import sys as _sys

        mod = _sys.modules.get(__name__)
        func = getattr(mod, "_run_impacted_or_full", None)
        orig = getattr(mod, "ORIG_RUN_IMPACTED_OR_FULL", None)
        if callable(func) and orig is not None and func is not orig:
            return func(
                self.project_root,
                cycle_idx=cycle_idx,
                full_every=full_every,
                on_event=on_event,
            )
        try_quick = (cycle_idx % max(1, full_every)) != 0
        changed = self._git_changed_files(on_event=on_event)
        if try_quick and changed:
            res = checks.run_quick_tests(changed, cwd=self.project_root)
            if not res.get("skipped") and res.get("ok") in (True, False):
                res_copy = dict(res)
                res_copy["mode"] = "quick"
                return res_copy
        out = self._run_tests_with_coverage(on_event=on_event)
        out["mode"] = "full"
        return out

    def _ensure_dashboard_dir(self, rebuild: bool = False) -> Path:
        d = self.project_root / MCP_DIR_NAME / DASHBOARD_SUBDIR
        if rebuild and d.exists():
            try:
                shutil.rmtree(d)
            except Exception:
                pass  # nosec B110 - defensive cleanup of temp dashboard dir
        d.mkdir(parents=True, exist_ok=True)
        return d

    def compute_status(self) -> Dict[str, object]:
        plan_text = ""
        try:
            plan_text = read_plan(self.project_root)
            status, current, nxt = parse_plan(plan_text)
            plan_obj = {"status": status, "current": current, "next": nxt}
        except Exception:
            plan_obj = {"status": "", "current": "", "next": ""}

        min_module = get_min_module(self.config, default=0.9)
        policy = get_coverage_policy(self.config)
        cov_summary = summarize(
            project_root=self.project_root, policy=policy, min_module=min_module
        )
        cov_groups = summarize_groups(
            project_root=self.project_root, policy=policy, min_module=min_module
        )
        cov_near = summarize_near(
            project_root=self.project_root, policy=policy, min_module=min_module
        )

        weak, groups, near, total_files = _coverage_with_fallback(
            self.project_root, cov_summary, cov_groups, cov_near
        )

        cov_progress = 0.0
        if total_files > 0:
            cov_progress = max(
                0.0, min(1.0, (total_files - len(weak)) / float(total_files))
            )

        done_count, pending_count, pending_tasks, done_tasks = _collect_tasks_counts(
            self.project_root, plan_text, include_docs=False
        )

        if plan_obj["status"] in ("planned", "") and pending_tasks:
            plan_obj["status"] = "in_progress"
            plan_obj["current"] = pending_tasks[0]

        plan_progress, overall = _compute_plan_overall(
            done_count, pending_count, cov_progress, len(pending_tasks)
        )

        prod_checks = {
            "coverage_gate": len(weak) == 0,
            "precommit_config": (
                self.project_root / ".pre-commit-config.yaml"
            ).exists(),
            "pre_push_hook": (self.project_root / ".git/hooks/pre-push").exists(),
            "plan_gate": (self.project_root / ".mcp/plan_gate.py").exists(),
            "branch_gate": (self.project_root / ".mcp/branch_name_gate.py").exists(),
            "ci_workflow": (self.project_root / ".github/workflows/ci.yml").exists(),
            "dockerfile": (self.project_root / "Dockerfile").exists(),
            "devcontainer": (
                self.project_root / ".devcontainer/devcontainer.json"
            ).exists(),
        }
        prod_progress = (
            sum(1 for v in prod_checks.values() if v) / float(len(prod_checks))
            if prod_checks
            else 0.0
        )

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

    def _load_run_config(self) -> Dict[str, object]:
        """Load agent run configuration from environment variables."""
        return {
            "auto_commit": os.environ.get("DEV_AGENT_AUTOCOMMIT", "0")
            in ("1", "true", "True"),
            "auto_push": os.environ.get("DEV_AGENT_AUTOPUSH", "0")
            in ("1", "true", "True"),
            "commit_interval": int(os.environ.get("DEV_AGENT_COMMIT_INTERVAL", "600")),
            "bypass_enabled": os.environ.get("DEV_AGENT_BYPASS", "1")
            in ("1", "true", "True"),
            "bypass_threshold": int(os.environ.get("DEV_AGENT_BYPASS_THRESHOLD", "3")),
            "bypass_allow_commit": os.environ.get("DEV_AGENT_BYPASS_COMMIT", "0")
            in ("1", "true", "True"),
            "bypass_state_file": self.project_root
            / MCP_DIR_NAME
            / DASHBOARD_SUBDIR
            / "bypass_state.json",
            "auto_tag": os.environ.get("DEV_AGENT_AUTOTAG", "0")
            in ("1", "true", "True"),
        }

    def _initialize_run_status(self, dash: Path, interval: int) -> None:
        """Run initial checks and write the first status file."""
        try:
            initial_tests = self._run_impacted_or_full(cycle_idx=0, full_every=1)
        except Exception:
            initial_tests = {
                "ok": False,
                "code": 1,
                "stdout": "",
                "stderr": "",
                "mode": "full",
            }
        try:
            initial_status = self.compute_status()
        except Exception:
            initial_status = {"plan": {}, "coverage": {}, "progress": {}, "tasks": {}}
        initial_status["timestamp"] = time.time()
        initial_status["tests"] = initial_tests
        initial_status["interval"] = interval

        try:
            txt0 = json.dumps(initial_status, ensure_ascii=False)
            atomic_write_text(dash / STATUS_FILE, txt0)
        except Exception:
            pass  # nosec B110 - Ignore initial write failure to keep agent alive

    def _run_quick_status_check(
        self,
        cmd: list[str],
        *,
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        """Helper to run a quick status check command."""
        try:
            try:
                p = run_cmd(
                    cmd,
                    cwd=self.project_root,
                    capture_stdout=True,
                    on_event=on_event,
                )
            except TypeError:
                p = run_cmd(
                    cmd,
                    cwd=self.project_root,
                    capture_stdout=True,
                )
            return "ok" if p.returncode == 0 else "fail"
        except Exception:
            return "skipped"

    def _run_cycle_checks(
        self, *, on_event: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, str]:
        """Run periodic checks like lint, type, and TDD gates."""
        lint_stat = self._run_quick_status_check(
            ["ruff", "check", "--quiet", "mcp_rules_assistant"], on_event=on_event
        )
        type_stat = self._run_quick_status_check(
            [
                "mypy",
                "mcp_rules_assistant/config.py",
                "mcp_rules_assistant/progress.py",
                "mcp_rules_assistant/tools.py",
                "mcp_rules_assistant/memory.py",
                "mcp_rules_assistant/mcp_server.py",
                "mcp_rules_assistant/cli.py",
                "mcp_rules_assistant/server.py",
            ],
            on_event=on_event,
        )
        tdd_script = self.project_root / ".mcp/tdd_gate.py"
        tdd_stat = (
            self._run_quick_status_check(["python", str(tdd_script)], on_event=on_event)
            if tdd_script.exists()
            else "skipped"
        )
        return {"lint": lint_stat, "type": type_stat, "tdd": tdd_stat}

    def _tests_failure_signature(self, tests: Dict[str, object]) -> str:
        """Stable, short failure signature for counting repeated failures."""
        return f"{tests.get('code')}|{str(tests.get('stderr',''))[:120]}|{str(tests.get('stdout',''))[:120]}"

    def _default_bypass_state(self, run_config: Dict[str, object]) -> BypassState:
        return {
            "active": False,
            "count": 0,
            "threshold": int(cast(Any, run_config.get("bypass_threshold", 0)) or 0),
            "since": "",
            "signature": "",
        }

    def _apply_bypass_effects(
        self,
        tests: Dict[str, object],
        run_config: Dict[str, object],
        bypass: BypassState,
    ) -> None:
        if bypass.get("active"):
            tests["bypassed"] = True
            if run_config.get("bypass_allow_commit"):
                tests["ok"] = True

    def _update_bypass_status(
        self, tests: Dict[str, object], run_config: Dict[str, object]
    ) -> Tuple[Dict[str, object], Dict[str, object]]:
        """Update the test bypass status based on repeated failures."""
        bypass_state_file = run_config.get("bypass_state_file")
        bypass: BypassState = self._default_bypass_state(run_config)
        if isinstance(bypass_state_file, Path):
            try:
                st = self._read_json(bypass_state_file)
                if isinstance(st, dict):
                    # best-effort: external file may not strictly match BypassState
                    bypass.update(cast(Any, st))
            except Exception:
                pass  # nosec B110 - ignore read failure, use previous stable coverage

        if not bool(tests.get("ok", False)):
            sig = self._tests_failure_signature(tests)
            current_count = bypass.get("count", 0)
            if sig == bypass.get("signature"):
                bypass["count"] = (
                    int(current_count) + 1 if isinstance(current_count, int) else 1
                )
            else:
                # accumulate across signature changes to keep hysteresis visible
                base = int(current_count) if isinstance(current_count, int) else 0
                bypass["count"] = base + 1
                bypass["signature"] = sig
                bypass["since"] = time.strftime("%Y-%m-%d %H:%M:%S")

            current_count = bypass.get("count", 0)
            thr = int(cast(Any, run_config.get("bypass_threshold", 0)) or 0)
            if (
                run_config.get("bypass_enabled")
                and isinstance(current_count, int)
                and current_count >= thr
            ):
                bypass["active"] = True
        else:
            bypass = self._default_bypass_state(run_config)

        self._apply_bypass_effects(tests, run_config, bypass)
        return tests, cast(Dict[str, object], bypass)

    def _build_current_status(
        self,
        tests: Dict[str, object],
        bypass: Dict[str, object],
        checks: Dict[str, str],
        interval: int,
        *,
        cmd_error_count: int = 0,
    ) -> Dict[str, object]:
        """Assemble the main status object for the current cycle."""
        status: Dict[str, object] = {
            "timestamp": time.time(),
            "tests": tests,
        }
        try:
            status.update(self.compute_status())
        except Exception as e:
            status["error"] = f"status compute failed: {e}"
        status["bypass"] = bypass
        status["interval"] = interval
        status["checks"] = {
            STEP_LINT: checks.get(STEP_LINT),
            STEP_TYPE: checks.get(STEP_TYPE),
            STEP_TESTS: "ok" if bool(tests.get("ok")) else "fail",
            STEP_TDD: checks.get(STEP_TDD),
        }
        return status

    def _update_failure_and_freeze_status(
        self, status: Dict[str, object], dash: Path
    ) -> None:
        """Update failure counters and freeze status based on current checks."""

        def _load_fail_state(fp: Path) -> tuple[FailCounters, LastTrigger, FreezeState]:
            fs = self._read_json(fp)
            _counters = fs.get("counters", {})
            cnt0: FailCounters = (
                cast(FailCounters, _counters)
                if isinstance(_counters, dict)
                else cast(FailCounters, {})
            )
            _last = fs.get("last_trigger", {})
            last0: LastTrigger = (
                cast(LastTrigger, _last)
                if isinstance(_last, dict)
                else cast(LastTrigger, {})
            )
            _freeze = fs.get("freeze", {})
            if isinstance(_freeze, dict) and _freeze:
                fr: FreezeState = _freeze  # type: ignore[assignment]
            else:
                fr = {"active": False, "since": "", "reason": ""}
            return cnt0, last0, fr

        def _bump_counters(cnt: FailCounters, last: LastTrigger) -> None:
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            checks_state = status.get("checks", {})
            tests_state = status.get("tests", {})
            if isinstance(checks_state, dict):
                if checks_state.get(STEP_LINT) == "fail":
                    cnt["lint"] = int(cnt.get("lint", 0)) + 1
                    last["lint"] = now_str
                if checks_state.get(STEP_TESTS) == "fail":
                    cnt["tests"] = int(cnt.get("tests", 0)) + 1
                    last["tests"] = now_str
            if isinstance(tests_state, dict):
                build_fail = (
                    (tests_state.get("code", 0) not in (0, 1))
                    and tests_state.get("mode") == "full"
                ) or (tests_state.get("code") == 127)
                if build_fail:
                    cnt["build"] = int(cnt.get("build", 0)) + 1
                    last["build"] = now_str
            if bool(status.get("error")):
                cnt["severe"] = int(cnt.get("severe", 0)) + 1
                last["severe"] = now_str

        def _maybe_activate_freeze(
            cnt: FailCounters, freeze: FreezeState
        ) -> FreezeState:
            thr = {
                "lint": int(os.environ.get("DEV_AGENT_THR_LINT", "15") or 15),
                "tests": int(os.environ.get("DEV_AGENT_THR_TESTS", "10") or 10),
                "build": int(os.environ.get("DEV_AGENT_THR_BUILD", "5") or 5),
                "severe": int(os.environ.get("DEV_AGENT_THR_SEVERE", "3") or 3),
            }
            if not freeze.get("active") and (
                int(cnt.get("tests", 0)) >= thr["tests"]
                or int(cnt.get("build", 0)) >= thr["build"]
                or int(cnt.get("severe", 0)) >= thr["severe"]
            ):
                return {
                    "active": True,
                    "since": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "reason": "threshold_reached",
                }
            return freeze

        def _weak_count_now() -> int:
            try:
                coverage_status = status.get("coverage", {})
                return len(
                    coverage_status.get("weak", [])
                    if isinstance(coverage_status, dict)
                    else []
                )
            except Exception:
                return 0

        def _maybe_recover_freeze(
            freeze: FreezeState, cnt: FailCounters
        ) -> tuple[FreezeState, FailCounters]:
            checks_state = status.get("checks", {})
            tests_state = status.get("tests", {})
            if (
                freeze.get("active")
                and isinstance(tests_state, dict)
                and bool(tests_state.get("ok"))
                and _weak_count_now() == 0
                and isinstance(checks_state, dict)
                and checks_state.get(STEP_LINT) == "ok"
                and (
                    checks_state.get(STEP_TYPE) in ("ok", "skipped")
                    if isinstance(checks_state, dict)
                    else False
                )
            ):
                return {
                    "active": False,
                    "since": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "reason": "recovered",
                }, cast(
                    FailCounters,
                    {"lint": 0, "tests": 0, "build": 0, "severe": 0},
                )
            return freeze, cnt

        def _persist_fail_state(
            fp: Path, cnt: FailCounters, last: LastTrigger, freeze: FreezeState
        ) -> None:
            try:
                atomic_write_text(
                    fp,
                    json.dumps(
                        {"counters": cnt, "last_trigger": last, "freeze": freeze},
                        ensure_ascii=False,
                    ),
                )
            except Exception:
                pass

        fail_state_file = dash / FAIL_COUNTERS_FILE
        cnt, last, freeze = _load_fail_state(fail_state_file)
        _bump_counters(cnt, last)
        freeze = _maybe_activate_freeze(cnt, freeze)
        freeze, cnt = _maybe_recover_freeze(freeze, cnt)

        if freeze.get("active"):
            try:
                prev = self._read_json(dash / STATUS_FILE)
                if isinstance(prev.get("coverage", {}), dict):
                    status["coverage"] = prev.get("coverage")
            except Exception:
                pass

        status["freeze"] = freeze
        status["fail_counters"] = {
            "counters": cnt,
            "last_trigger": last,
            "thresholds": {
                "lint": int(os.environ.get("DEV_AGENT_THR_LINT", "15") or 15),
                "tests": int(os.environ.get("DEV_AGENT_THR_TESTS", "10") or 10),
                "build": int(os.environ.get("DEV_AGENT_THR_BUILD", "5") or 5),
                "severe": int(os.environ.get("DEV_AGENT_THR_SEVERE", "3") or 3),
            },
        }
        _persist_fail_state(dash / FAIL_COUNTERS_FILE, cnt, last, freeze)
        # brief status for lightweight consumers
        try:
            prog = status.get("progress")
            prog_overall = 0.0
            if isinstance(prog, dict):
                try:
                    prog_overall = float(prog.get("overall", 0.0))
                except Exception:
                    prog_overall = 0.0
            cov = status.get("coverage")
            weak_len = 0
            if isinstance(cov, dict):
                try:
                    w = cov.get("weak", [])
                    weak_len = len(w) if isinstance(w, list) else 0
                except Exception:
                    weak_len = 0
            ts = 0.0
            ts_raw = status.get("timestamp", 0.0)
            try:
                ts = float(ts_raw) if isinstance(ts_raw, (int, float, str)) else 0.0
            except Exception:
                ts = 0.0
            brief = {"overall": prog_overall, "weak_count": weak_len, "timestamp": ts}
            atomic_write_text(
                dash / "status_brief.json", json.dumps(brief, ensure_ascii=False)
            )
        except Exception:
            pass

    def _persist_status_and_history(
        self, status: Dict[str, object], dash: Path, t0: float
    ) -> None:
        """Write the main status file and update the history log."""
        try:
            txt = json.dumps(status, ensure_ascii=False)
            atomic_write_text(dash / STATUS_FILE, txt)
        except Exception:
            pass  # Ignore write failure to keep agent running

        try:
            progress_status = status.get("progress", {})
            overall_progress = (
                progress_status.get("overall", 0.0)
                if isinstance(progress_status, dict)
                else 0.0
            )
            coverage_progress = (
                progress_status.get("progress", 0.0)
                if isinstance(progress_status, dict)
                else 0.0
            )

            coverage_status = status.get("coverage", {})
            weak_coverage = (
                coverage_status.get("weak", [])
                if isinstance(coverage_status, dict)
                else []
            )

            checks_status = status.get("checks", {})
            bypass_status = status.get("bypass", {})

            rec = {
                "ts": status.get("timestamp"),
                "duration": max(0, time.time() - t0),
                "overall": overall_progress,
                "coverage_progress": coverage_progress,
                "coverage_weak": len(weak_coverage),
                "checks": checks_status,
                "bypass": bypass_status,
            }
            hist_p = dash / HISTORY_FILE
            arr = []
            if hist_p.exists():
                try:
                    arr = json.loads(hist_p.read_text(encoding="utf-8"))
                except Exception:
                    arr = []
            arr.append(rec)
            arr = arr[-50:]
            atomic_write_text(hist_p, json.dumps(arr, ensure_ascii=False))
        except Exception:
            pass  # nosec B110 - history write errors are non-fatal

    def _handle_auto_commit(
        self,
        tests: Dict[str, object],
        bypass: Dict[str, object],
        run_config: Dict[str, object],
        last_commit_ts: float,
        *,
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> float:
        """Handle automatic git commits if conditions are met."""
        bypass_allow_commit = run_config.get("bypass_allow_commit", False)
        auto_commit = run_config.get("auto_commit", False)
        commit_interval = run_config.get("commit_interval", 600)
        auto_push = run_config.get("auto_push", False)

        can_commit = bool(tests.get("ok")) or (
            bypass.get("active") and bypass_allow_commit
        )
        if (
            auto_commit
            and isinstance(commit_interval, int)
            and (time.time() - last_commit_ts) >= commit_interval
            and can_commit
        ):
            try:
                plan_text = read_plan(self.project_root)
                plan_status, cur, _ = parse_plan(plan_text)
                if plan_status == "in_progress" and cur:
                    try:
                        proc = run_cmd(
                            ["git", "status", "--porcelain"],
                            cwd=self.project_root,
                            capture_stdout=True,
                            on_event=on_event,
                        )
                    except TypeError:
                        proc = run_cmd(
                            ["git", "status", "--porcelain"],
                            cwd=self.project_root,
                            capture_stdout=True,
                        )
                    if (proc.stdout or "").strip():
                        try:
                            run_cmd(
                                ["git", "add", "-A"],
                                cwd=self.project_root,
                                capture_stdout=False,
                                check=False,
                                on_event=on_event,
                            )
                        except TypeError:
                            run_cmd(
                                ["git", "add", "-A"],
                                cwd=self.project_root,
                                capture_stdout=False,
                                check=False,
                            )
                        msg = f"chore(agent): auto update [step:{cur}]"
                        try:
                            run_cmd(
                                ["git", "commit", "-m", msg],
                                cwd=self.project_root,
                                capture_stdout=False,
                                check=False,
                                on_event=on_event,
                            )
                        except TypeError:
                            run_cmd(
                                ["git", "commit", "-m", msg],
                                cwd=self.project_root,
                                capture_stdout=False,
                                check=False,
                            )
                        if auto_push:
                            try:
                                run_cmd(
                                    ["git", "push"],
                                    cwd=self.project_root,
                                    capture_stdout=False,
                                    check=False,
                                    on_event=on_event,
                                )
                            except TypeError:
                                run_cmd(
                                    ["git", "push"],
                                    cwd=self.project_root,
                                    capture_stdout=False,
                                    check=False,
                                )
                        return time.time()
            except Exception:
                pass  # nosec B110 - auto-commit is best-effort
        return last_commit_ts

    def _handle_auto_tag(
        self,
        tests: Dict[str, object],
        status: Dict[str, object],
        run_config: Dict[str, object],
        last_tag_date: str,
        *,
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        """Handle automatic git tagging if conditions are met."""
        auto_tag = run_config.get("auto_tag", False)
        if auto_tag and tests.get("ok") and tests.get("mode") == "full":
            try:
                coverage_status = status.get("coverage", {})
                weak = (
                    coverage_status.get("weak", [])
                    if isinstance(coverage_status, dict)
                    else []
                )
                if not weak:
                    today = time.strftime("%Y%m%d", time.localtime())
                    if today != last_tag_date:
                        tag = f"v{PKG_VERSION}-dev{today}"
                        try:
                            p = run_cmd(
                                ["git", "tag", "-l", tag],
                                cwd=self.project_root,
                                capture_stdout=True,
                                on_event=on_event,
                            )
                        except TypeError:
                            p = run_cmd(
                                ["git", "tag", "-l", tag],
                                cwd=self.project_root,
                                capture_stdout=True,
                            )
                        if tag not in (p.stdout or ""):
                            try:
                                run_cmd(
                                    [
                                        "git",
                                        "tag",
                                        "-a",
                                        tag,
                                        "-m",
                                        f"auto dev milestone {today}",
                                    ],
                                    cwd=self.project_root,
                                    capture_stdout=False,
                                    check=False,
                                    on_event=on_event,
                                )
                            except TypeError:
                                run_cmd(
                                    [
                                        "git",
                                        "tag",
                                        "-a",
                                        tag,
                                        "-m",
                                        f"auto dev milestone {today}",
                                    ],
                                    cwd=self.project_root,
                                    capture_stdout=False,
                                    check=False,
                                )
                            return today
            except Exception:
                pass  # nosec B110 - auto-tag is best-effort
        return last_tag_date

    # removed: internal atomic helper in favor of fs_wrapper.atomic_write_text

    def run(self, interval: int, max_cycles: int = 0):
        # 兼容测试对模块级 _ensure_dashboard_dir 的 monkeypatch，同时避免 __main__ 顺序问题
        try:
            # 若实例级别被 monkeypatch（存在于 __dict__），优先使用实例方法
            if "_ensure_dashboard_dir" in getattr(self, "__dict__", {}):
                dash = self._ensure_dashboard_dir(rebuild=True)  # type: ignore[misc]
            else:
                import mcp_rules_assistant.dev_agent as _dev_mod

                _func = getattr(_dev_mod, "_ensure_dashboard_dir", None)
                if callable(_func):  # 模块级 monkeypatch（测试常用模式）
                    dash = _func(self.project_root, rebuild=True)  # type: ignore[misc]
                else:
                    dash = self._ensure_dashboard_dir(rebuild=True)
        except Exception:
            # 最后回退：确保目录存在
            dash = self.project_root / ".mcp" / "dashboard"
            dash.mkdir(parents=True, exist_ok=True)
        self._initialize_run_status(dash, interval)

        run_config = self._load_run_config()
        last_commit_ts = 0.0
        last_tag_date = ""

        cycle = 0
        while True:
            if max_cycles and cycle >= max_cycles:
                break

            t0 = time.time()
            cmd_events: List[Dict[str, Any]] = []

            def _on_evt(evt: Dict[str, Any]) -> None:
                try:
                    evt = dict(evt)
                    evt["ts"] = time.time()
                    # keep minimal set
                    evt["cmd"] = " ".join([str(x) for x in (evt.get("cmd") or [])])
                    cmd_events.append(evt)
                except Exception:
                    pass

            # 1. Run tests and checks
            tests = self._run_impacted_or_full(
                cycle_idx=cycle, full_every=5, on_event=_on_evt
            )
            try:
                checks = self._run_cycle_checks(on_event=_on_evt)
            except TypeError:
                checks = self._run_cycle_checks()

            # 2. Update bypass status
            tests, bypass = self._update_bypass_status(tests, run_config)

            # 3. Build status object
            err_count = sum(1 for e in cmd_events if e.get("phase") == "error")
            status = self._build_current_status(
                tests, bypass, checks, interval, cmd_error_count=err_count
            )

            # 4. Update failure counters and freeze status
            self._update_failure_and_freeze_status(status, dash)

            # 5. Persist status and history
            self._persist_status_and_history(status, dash, t0)

            # 6. Handle auto-commit and auto-tag
            last_commit_ts = self._handle_auto_commit(
                tests, bypass, run_config, last_commit_ts, on_event=_on_evt
            )
            last_tag_date = self._handle_auto_tag(
                tests, status, run_config, last_tag_date, on_event=_on_evt
            )

            # 6.1 Persist command events (best-effort, cap to last 200) + JSONL append
            try:
                ce_path = dash / "cmd_events.json"
                prev: List[Dict[str, Any]] = []
                if ce_path.exists():
                    try:
                        prev = json.loads(ce_path.read_text(encoding="utf-8")) or []
                    except Exception:
                        prev = []
                merged = (prev + cmd_events)[-200:]
                atomic_write_text(ce_path, json.dumps(merged, ensure_ascii=False))
                try:
                    jlines = "".join(
                        json.dumps(e, ensure_ascii=False) + "\n" for e in cmd_events
                    )
                    if jlines:
                        with (dash / "cmd_events.jsonl").open(
                            "a", encoding="utf-8"
                        ) as jf:
                            jf.write(jlines)
                except Exception:
                    pass
            except Exception:
                pass

            # 7. Wait for next cycle
            dt = max(1, interval - int(time.time() - t0))
            time.sleep(dt)
            cycle += 1


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser("dev-agent")
    ap.add_argument("--interval", type=int, default=60, help="run interval seconds")
    ap.add_argument("--max-cycles", type=int, default=0, help="max cycles to run")
    args = ap.parse_args(argv)

    agent = DevAgent(project_root=Path.cwd().resolve())
    # Fallback to environment to honor tests and CLI-less invocations
    env_max = 0
    try:
        env_max = int(os.environ.get("DEV_AGENT_MAX_CYCLES", "0") or "0")
    except Exception:
        env_max = 0
    max_cycles = args.max_cycles if args.max_cycles > 0 else env_max
    agent.run(interval=args.interval, max_cycles=max_cycles)


if __name__ == "__main__":
    main()

# --------------------------------------------------------------------------------------
# Module-level helper functions kept for backward-compat with tests and external scripts
# These mirror DevAgent methods but operate with an explicit project_root argument.


def _run_tests_with_coverage(
    project_root: Path, *, on_event: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, object]:
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
        p = run_cmd(
            cmd,
            cwd=project_root,
            capture_stdout=True,
            env=env,
            on_event=on_event,
        )
        return {
            "ok": p.returncode == 0,
            "code": p.returncode,
            "stdout": (p.stdout or "")[-8000:],
            "stderr": (p.stderr or "")[-8000:],
            "cmd": cmd,
        }
    except FileNotFoundError:
        return {"ok": False, "code": 127, "error": "python/pytest not found"}


def _git_changed_files(
    project_root: Path, *, on_event: Optional[Callable[[Dict[str, Any]], None]] = None
) -> list[Path]:
    try:
        p = run_cmd(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            capture_stdout=True,
            on_event=on_event,
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


def _run_impacted_or_full(
    project_root: Path,
    *,
    cycle_idx: int,
    full_every: int = 5,
    on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, object]:
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


# Keep a reference to the original function for test-detection in instance method
ORIG_RUN_IMPACTED_OR_FULL = _run_impacted_or_full


def run_impacted_or_full(
    project_root: Path, *, cycle_idx: int, full_every: int = 5
) -> Dict[str, object]:
    """Public wrapper for running impacted or full test cycles.

    This simply forwards to the internal helper to preserve behavior while
    providing a stable public API for tests and external callers.
    """
    return _run_impacted_or_full(
        project_root, cycle_idx=cycle_idx, full_every=full_every
    )


def _scan_markdown_checklist(p: Path) -> Tuple[int, int, list[str], list[str]]:
    """Scan a markdown file for checklist items (done/pending), ignoring code blocks.

    Returns: (done_count, pending_count, pending_items, done_items)
    """
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


# Public test-friendly wrappers for selected DevAgent behaviors
def get_run_config(agent: "DevAgent") -> Dict[str, object]:
    """Public wrapper to load run configuration for an agent instance."""
    return agent._load_run_config()


def auto_commit(
    agent: "DevAgent",
    tests: Dict[str, object],
    bypass: Dict[str, object],
    run_config: Dict[str, object],
    last_commit_ts: float,
) -> float:
    """Public wrapper to trigger auto-commit logic once and return last_commit_ts."""
    return agent._handle_auto_commit(tests, bypass, run_config, last_commit_ts)


def auto_tag(
    agent: "DevAgent",
    tests: Dict[str, object],
    status: Dict[str, object],
    run_config: Dict[str, object],
    last_tag_date: str,
) -> str:
    """Public wrapper to trigger auto-tag logic once and return last_tag_date."""
    return agent._handle_auto_tag(tests, status, run_config, last_tag_date)


def _ensure_dashboard_dir(project_root: Path, rebuild: bool = False) -> Path:
    d = project_root / ".mcp" / "dashboard"
    if rebuild and d.exists():
        try:
            shutil.rmtree(d)
        except Exception:
            # best-effort cleanup
            pass  # nosec B110
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_json(p: Path) -> Dict[str, Any]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _coverage_with_fallback(
    project_root: Path,
    cov_summary: Dict[str, object],
    cov_groups: Dict[str, object],
    cov_near: Dict[str, object],
) -> Tuple[
    list[Dict[str, object]], list[Dict[str, object]], list[Dict[str, object]], int
]:
    """Extract coverage arrays with a fallback to last dashboard status when count==0.

    Returns: (weak, groups, near, total_files)
    """
    raw_weak = cov_summary.get("weak") if isinstance(cov_summary, dict) else []
    weak: list[Dict[str, object]] = []
    if isinstance(raw_weak, list):
        weak = [cast(Dict[str, object], x) for x in raw_weak if isinstance(x, dict)]

    raw_groups = cov_groups.get("groups") if isinstance(cov_groups, dict) else []
    groups: list[Dict[str, object]] = []
    if isinstance(raw_groups, list):
        groups = [cast(Dict[str, object], x) for x in raw_groups if isinstance(x, dict)]

    raw_near = cov_near.get("near") if isinstance(cov_near, dict) else []
    near: list[Dict[str, object]] = []
    if isinstance(raw_near, list):
        near = [cast(Dict[str, object], x) for x in raw_near if isinstance(x, dict)]

    raw_total_files = cov_summary.get("count") if isinstance(cov_summary, dict) else 0
    total_files = (
        int(raw_total_files)
        if isinstance(raw_total_files, (int, float, str))
        and str(raw_total_files).isdigit()
        else 0
    )

    if total_files == 0:
        prev = _read_json(project_root / MCP_DIR_NAME / DASHBOARD_SUBDIR / STATUS_FILE)
        _cp = prev.get("coverage", {})
        cov_prev: Dict[str, Any] = _cp if isinstance(_cp, dict) else {}

        fallback_weak = cov_prev.get("weak", weak)
        if isinstance(fallback_weak, list):
            weak = [
                cast(Dict[str, object], x) for x in fallback_weak if isinstance(x, dict)
            ]

        fallback_groups = cov_prev.get("groups", groups)
        if isinstance(fallback_groups, list):
            groups = [
                cast(Dict[str, object], x)
                for x in fallback_groups
                if isinstance(x, dict)
            ]

        fallback_near = cov_prev.get("near", near)
        if isinstance(fallback_near, list):
            near = [
                cast(Dict[str, object], x) for x in fallback_near if isinstance(x, dict)
            ]

        fallback_total = cov_prev.get("count", 0)
        try:
            total_files = int(fallback_total)  # best effort
        except Exception:
            total_files = 0

    return weak, groups, near, total_files


def _collect_tasks_counts(
    project_root: Path, plan_text: str, *, include_docs: bool = True
) -> Tuple[int, int, list[str], list[str]]:
    """Collect done/pending tasks counts and lists by scanning markdown and fallback plan sections.

    Returns: (done_count, pending_count, pending_tasks, done_tasks)
    """
    pending_tasks: list[str] = []
    done_tasks: list[str] = []
    done_count = 0
    pending_count = 0
    try:
        d0, u0, p0, dn0 = _scan_markdown_checklist(
            project_root / f"{MCP_DIR_NAME}/plan.md"
        )
        done_count += d0
        pending_count += u0
        pending_tasks.extend(p0)
        done_tasks.extend(dn0)
        if include_docs:
            for p in (project_root / "docs").glob("*.md"):
                d1, u1, p1, dn1 = _scan_markdown_checklist(p)
                done_count += d1
                pending_count += u1
                pending_tasks.extend(p1)
                done_tasks.extend(dn1)
            for p in [project_root / "README.md"]:
                if p.exists():
                    d2, u2, p2, dn2 = _scan_markdown_checklist(p)
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
                if any(k in low for k in ["待办", "next actions", "下一步"]):
                    capture = True
                    continue
                if capture:
                    if raw.strip().startswith("- "):
                        item = raw.strip()[2:].strip()
                        if item:
                            pending_tasks.append(item)
                    elif raw.strip() == "" or raw.startswith("#"):
                        break
            if pending_tasks:
                pending_count = len(pending_tasks)
                done_count = 0
    except Exception:
        pass  # nosec B110 - plan parsing failure falls back to zeros
    return done_count, pending_count, pending_tasks, done_tasks


def _compute_plan_overall(
    done_count: int, pending_count: int, cov_progress: float, pending_len: int
) -> Tuple[Optional[float], float]:
    """Compute plan_progress and overall score from counts and coverage progress.

    overall = cov_progress when no plan info; otherwise 0.6*coverage + 0.4*plan.
    """
    plan_progress: Optional[float] = None
    if done_count + pending_count == 0 and pending_len > 0:
        pending_count = pending_len
        done_count = 0
    if done_count + pending_count > 0:
        plan_progress = done_count / float(done_count + pending_count)

    overall = cov_progress
    if plan_progress is not None:
        overall = 0.6 * cov_progress + 0.4 * float(plan_progress)
    return plan_progress, overall


def update_bypass(
    agent: "DevAgent",
    tests: Dict[str, object],
    run_config: Dict[str, object],
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Public wrapper to update bypass status for a given tests result.

    Returns (tests, bypass) where tests may be modified (e.g., bypassed/ok).
    """
    return agent._update_bypass_status(tests, run_config)


def update_failure_and_freeze(
    agent: "DevAgent",
    status: Dict[str, object],
    dash: Path,
) -> Dict[str, object]:
    """Public wrapper to update failure counters and freeze logic in-place.

    Returns the mutated status for convenience.
    """
    agent._update_failure_and_freeze_status(status, dash)
    return status


def compute_status(project_root: Path) -> Dict[str, object]:
    # Load config defensively (tests may monkeypatch to raise)
    try:
        cfg = load_config(project_root)
    except Exception:
        cfg = {}

    plan_text = ""
    try:
        plan_text = read_plan(project_root)
        status, current, nxt = parse_plan(plan_text)
        plan_obj = {"status": status, "current": current, "next": nxt}
    except Exception:
        plan_obj = {"status": "", "current": "", "next": ""}

    min_module = get_min_module(cfg, default=0.9)
    policy = get_coverage_policy(cfg)

    cov_summary = summarize(
        project_root=project_root, policy=policy, min_module=min_module
    )
    cov_groups = summarize_groups(
        project_root=project_root, policy=policy, min_module=min_module
    )
    cov_near = summarize_near(
        project_root=project_root, policy=policy, min_module=min_module
    )

    weak, groups, near, total_files = _coverage_with_fallback(
        project_root, cov_summary, cov_groups, cov_near
    )

    cov_progress = 0.0
    if total_files > 0:
        cov_progress = max(
            0.0, min(1.0, (total_files - len(weak)) / float(total_files))
        )

    done_count, pending_count, pending_tasks, done_tasks = _collect_tasks_counts(
        project_root, plan_text, include_docs=False
    )

    if plan_obj["status"] in ("planned", "") and pending_tasks:
        plan_obj["status"] = "in_progress"
        plan_obj["current"] = pending_tasks[0]

    plan_progress, overall = _compute_plan_overall(
        done_count, pending_count, cov_progress, len(pending_tasks)
    )

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
    prod_progress = (
        sum(1 for v in prod_checks.values() if v) / float(len(prod_checks))
        if prod_checks
        else 0.0
    )

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
        "tasks": {"pending": pending_tasks[:20], "done": done_tasks[:20]},
    }
