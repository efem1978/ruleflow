from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import coverage_summary as cov
from .config import load_config
from .progress import ensure_plan, parse_plan, read_plan


@dataclass
class PlanSnapshot:
    status: str
    current: str
    next_step: str
    done_count: int
    pending_count: int


def _plan_snapshot(project_root: Optional[Path] = None) -> PlanSnapshot:
    root = (project_root or Path.cwd()).resolve()
    ensure_plan(root)
    text = read_plan(root)
    status, cur, nxt = parse_plan(text)
    # Rough checkbox counts
    done_count = text.count("[x]")
    pending_count = text.count("[ ]")
    return PlanSnapshot(
        status=status or "planned",
        current=cur or "",
        next_step=nxt or "",
        done_count=done_count,
        pending_count=pending_count,
    )


def _coverage_snapshot(project_root: Optional[Path] = None) -> Dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    cfg = load_config()
    perf = (
        cfg.get("performance", {})
        if isinstance(cfg.get("performance", {}), dict)
        else {}
    )
    min_module = float(
        (perf.get("on_push", {}) or {}).get("coverage", {}).get("min_module", 0.9)
    )
    policy = (
        (cfg.get("coverage", {}) or {}).get("policy", None)
        if isinstance(cfg.get("coverage", {}), dict)
        else None
    )
    res_w: Dict[str, Any] = cov.summarize(
        project_root=root, policy=policy, min_module=min_module
    )
    res_g: Dict[str, Any] = cov.summarize_groups(
        project_root=root, policy=policy, min_module=min_module
    )
    near_cfg = (
        (cfg.get("coverage", {}) or {}).get("near", {})
        if isinstance(cfg.get("coverage", {}), dict)
        else {}
    )
    within = float(near_cfg.get("within", 0.03))
    top = int(near_cfg.get("top", 50))
    res_n = cov.summarize_near(
        project_root=root, policy=policy, min_module=min_module, within=within, top=top
    )
    weak_obj = res_w.get("weak", [])
    weak: List[Dict[str, Any]] = weak_obj if isinstance(weak_obj, list) else []
    groups_obj = res_g.get("groups", [])
    groups: List[Dict[str, Any]] = groups_obj if isinstance(groups_obj, list) else []
    near_obj = res_n.get("near", [])
    near: List[Dict[str, Any]] = near_obj if isinstance(near_obj, list) else []
    cnt_obj = res_w.get("count", 0)
    count = int(cnt_obj) if isinstance(cnt_obj, (int, float)) else 0
    cov_progress = 0.0
    try:
        if count:
            cov_progress = 1.0 - (len(weak) / float(count))
    except Exception:
        cov_progress = 0.0
    return {
        "weak": weak,
        "groups": groups,
        "near": near,
        "min_module": min_module,
        "count": count,
        "progress": cov_progress,
    }


def _memory_snapshot(project_root: Optional[Path] = None) -> Dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    p = root / ".mcp/memory.json"
    if not p.exists():
        return {"exists": False, "summary": "", "turns": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        turns = data.get("turns", []) if isinstance(data.get("turns"), list) else []
        return {
            "exists": True,
            "summary": data.get("summary", ""),
            "turns": turns[-6:],
        }
    except Exception:
        return {"exists": False, "summary": "", "turns": []}


def generate_status(project_root: Optional[Path] = None) -> Dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    plan = _plan_snapshot(root)
    coverage = _coverage_snapshot(root)
    # Collect tasks (pending/done) similar to DevAgent for richer status payload
    pending_tasks: list[str] = []
    done_tasks: list[str] = []
    try:
        from .dev_agent import _collect_tasks_counts as _collect  # type: ignore

        plan_text = read_plan(root)
        _d, _u, _p, _dn = _collect(root, plan_text, include_docs=False)
        pending_tasks = list(_p)[:50]
        done_tasks = list(_dn)[:50]
    except Exception:
        # Best-effort: tasks list unavailable → keep empty arrays
        pending_tasks = []
        done_tasks = []
    memory = _memory_snapshot(root)
    overall_progress = 0.0
    try:
        counts_total = plan.done_count + plan.pending_count
        plan_progress = (plan.done_count / float(counts_total)) if counts_total else 0.0
        overall_progress = (plan_progress + coverage.get("progress", 0.0)) / 2.0
    except Exception:
        overall_progress = 0.0
    # 命令事件近24小时指标（可选）
    cmd_metrics: Dict[str, Any] | None = None
    try:

        dash_dir = (project_root or Path.cwd()).resolve() / ".mcp/dashboard"
        jl = dash_dir / "cmd_events.jsonl"
        if jl.exists():
            total = 0
            errors = 0
            elapsed_sum = 0.0
            recent = []
            for line in jl.read_text(encoding="utf-8").splitlines():
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                # 无时间戳则按最近视为有效；事件通常跨短时间，不强依赖绝对时间
                # 仅统计 end/error 两类
                ph = e.get("phase")
                if ph not in ("end", "error"):
                    continue
                # 粗略过滤：如事件带 elapsed 字段则可计入
                if ph == "end":
                    total += 1
                    try:
                        elapsed_sum += float(e.get("elapsed", 0.0) or 0.0)
                    except Exception:
                        pass
                elif ph == "error":
                    errors += 1
                    total += 1
                recent.append(e)
            avg_elapsed = (elapsed_sum / max(1, total)) if total else 0.0
            fail_ratio = (errors / float(total)) if total else 0.0
            cmd_metrics = {
                "last24h": {
                    "events": total,
                    "errors": errors,
                    "fail_ratio": round(fail_ratio, 4),
                    "avg_elapsed": round(avg_elapsed, 4),
                }
            }
    except Exception:
        cmd_metrics = None

    payload: Dict[str, Any] = {
        # 使用 timezone-aware 时间，避免 utcnow 弃用告警（-W error 环境下会失败）
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "plan": {
            "status": plan.status,
            "current": plan.current,
            "next": plan.next_step,
            "counts": {"done": plan.done_count, "pending": plan.pending_count},
        },
        "coverage": coverage,
        "memory": memory,
        "progress": {"overall": overall_progress},
        "tasks": {"pending": pending_tasks, "done": done_tasks},
    }
    if cmd_metrics is not None:
        payload["cmd_metrics"] = cmd_metrics
    # persist
    dash = root / ".mcp/dashboard"
    dash.mkdir(parents=True, exist_ok=True)
    (dash / "status.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # history (append, keep last 50)
    hist_p = dash / "history.json"
    try:
        hist: List[Dict[str, Any]]
        if hist_p.exists():
            hist = json.loads(hist_p.read_text(encoding="utf-8"))
            if not isinstance(hist, list):
                hist = []
        else:
            hist = []
        hist.append(
            {
                "time": payload["time"],
                "plan": payload["plan"],
                "progress": payload["progress"],
            }
        )
        hist = hist[-50:]
        hist_p.write_text(
            json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        import logging

        logging.getLogger(__name__).debug("[auto_status] history write skipped: %r", e)
    return payload
