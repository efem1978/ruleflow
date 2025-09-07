from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

import yaml

from . import checks as checks_mod
from . import coverage_summary as covsum
from . import hooks as hooks_mod
from . import nl as nl_mod
from . import progress as progress_mod
from . import rules_ingest as ri
from .config import DEFAULT_PROJECT_CONFIG_PATH, ensure_project_config, load_config
from .fs_wrapper import FSGuard, atomic_write_text
from .memory import MemoryManager
from .policy_keys import (
    POLICY_KEY_CONTAINER_BASELINE,
    POLICY_KEY_CONTAINER_REQUIRED,
    POLICY_KEY_SECURITY_SAST_STRICT,
    POLICY_KEY_SECURITY_SECRETS_SCAN,
)
from .process import run_cmd
from .rules import Complexity, DevMode, Scenario, choose_thresholds, explain_thresholds
from .tools import registry, setup_default_tools

# MIME constants
MIME_JSON = "application/json"
MIME_MD = "text/markdown"
MIME_YAML = "text/yaml"

# Policy key constants centralized in policy_keys


def _read_stdin_lines() -> List[str]:
    return sys.stdin.read().splitlines()


class JsonRpcServer:
    """极简 JSON-RPC 2.0 stdio 服务器（MCP 风格方法名）。

    说明：此为教学与骨架用途，不含完整错误分类与并发/流控。
    """

    def __init__(self) -> None:
        setup_default_tools()
        self.project_root = Path.cwd()
        self.mm = MemoryManager(self.project_root)
        self.fs = FSGuard(self.project_root)
        self.settings: Dict[str, Any] = {"memory_auto": False}
        self.cfg = load_config(self.project_root)

    # ---- MCP-like methods ----
    def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})
        result: Dict[str, Any] = {}
        try:
            if method == "initialize":
                # 声明最小能力集，含 prompts（提供占位端点）
                caps: Dict[str, Any] = {
                    "tools": True,
                    "resources": True,
                    "prompts": True,
                }
                result = {
                    "server": "mcp-rules-assistant",
                    "version": "0.1.0",
                    "capabilities": caps,
                }
            elif method == "ping":
                result = {"ok": True}
            elif method == "tools/list":
                tool_items: List[Dict[str, Any]] = [
                    (
                        asdict(t)
                        if hasattr(t, "__dict__")
                        else {"name": t.name, "description": t.description}
                    )
                    for t in registry.list()
                ]
                result = {"tools": tool_items}
            elif method == "tools/call":
                name = params.get("name")
                args = params.get("arguments", {})
                result = self._call_tool(name, args)
            elif method == "resources/list":
                resources_list: List[Dict[str, str]] = [
                    {
                        "uri": f"memory://{self._project_id()}/rollup",
                        "name": "Last 20 turns & summary",
                    },
                    {
                        "uri": f"memory://{self._project_id()}/links",
                        "name": "Cross-project links",
                    },
                    {
                        "uri": f"rules://project/{self._project_id()}/compiled",
                        "name": "Compiled project rules",
                    },
                    {
                        "uri": f"rules://project/{self._project_id()}/compiled.json",
                        "name": "Compiled rules (JSON)",
                    },
                    {
                        "uri": f"rules://project/{self._project_id()}/suggestions",
                        "name": "Rule conflicts & suggestions",
                    },
                    {
                        "uri": f"rules://project/{self._project_id()}/maxima",
                        "name": "Coverage upper-bounds (maxima)",
                    },
                    {
                        "uri": f"coverage://project/{self._project_id()}/summary",
                        "name": "Coverage summary",
                    },
                    {
                        "uri": f"coverage://project/{self._project_id()}/groups",
                        "name": "Coverage groups",
                    },
                    {
                        "uri": f"coverage://project/{self._project_id()}/tree",
                        "name": "Coverage tree (weak)",
                    },
                    {
                        "uri": f"coverage://project/{self._project_id()}/near",
                        "name": "Coverage near threshold",
                    },
                    {
                        "uri": f"coverage://project/{self._project_id()}/report",
                        "name": "Coverage report (weak/groups/near)",
                    },
                    {
                        "uri": f"progress://{self._project_id()}/plan",
                        "name": "Project plan",
                    },
                    {
                        "uri": f"config://project/{self._project_id()}/assistant.yaml",
                        "name": "Project config (YAML)",
                    },
                    {
                        "uri": f"ci://project/{self._project_id()}/workflow",
                        "name": "CI workflow (YAML)",
                    },
                ]
                result = {"resources": resources_list}
            elif method == "resources/read":
                uri = params.get("uri", "")
                if uri.startswith("memory://"):
                    # Special-case links
                    if str(uri).endswith("/links"):
                        snap = self.mm.snapshot()
                        links = snap.get("links", []) if isinstance(snap, dict) else []
                        result = {
                            "mimeType": MIME_JSON,
                            "text": json.dumps({"links": links}, ensure_ascii=False),
                        }
                    else:
                        result = self._res_read_memory()
                elif uri.startswith("rules://"):
                    result = self._res_read_rules(uri)
                elif uri.startswith("coverage://"):
                    result = self._res_read_coverage(uri)
                elif uri.startswith("progress://"):
                    result = self._res_read_progress()
                elif uri.startswith("config://"):
                    result = self._res_read_config()
                elif uri.startswith("ci://"):
                    result = self._res_read_ci()
                else:
                    raise ValueError("Unknown resource uri")
            elif method == "prompts/list":
                # 最小占位：当前不提供内置提示，返回空列表
                result = {"prompts": []}
            elif method == "prompts/get":
                # 最小占位：返回不存在
                name = str(params.get("name", ""))
                result = {"ok": False, "message": f"prompt '{name}' not found"}
            else:
                raise ValueError(f"Unknown method: {method}")
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as e:  # noqa: BLE001 - simple skeleton
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(e)},
            }

    # ---- Tools implementations (skeleton) ----
    def _call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name == "project.detect":
            return self._tool_project_detect()
        if name == "project.switch":
            # arguments: { path?: string }
            new_path = args.get("path")
            if new_path:
                p = Path(new_path).expanduser().resolve()
                self.project_root = p
                # Rebind per-project helpers
                self.mm = MemoryManager(self.project_root)
                self.fs = FSGuard(self.project_root)
                self.cfg = load_config(self.project_root)
            return {"ok": True, "root": str(self.project_root)}
        if name == "project.link":
            target = str(args.get("project", "")).strip()
            task = str(args.get("task", "")).strip()
            note = str(args.get("note", "")).strip()
            if not target or not task:
                raise ValueError("project and task required")
            self.mm.add_link(target, task, note)
            return {"ok": True}
        if name == "memory.toggle_auto":
            on = bool(args.get("on", True))
            self.settings["memory_auto"] = on
            return {"ok": True, "auto": on}
        if name == "memory.snapshot":
            return self.mm.snapshot()
        if name == "memory.append_turn":
            role = str(args.get("role", "")).strip() or "user"
            content = str(args.get("content", ""))
            meta = args.get("meta", {})
            if not isinstance(meta, dict):
                meta = {}
            self.mm.append_turn(role, content, meta)
            return {"ok": True}
        if name == "rules.init":
            s = Scenario(args.get("scenario", "personal"))
            c = Complexity(args.get("complexity", "small"))
            dm = DevMode(args.get("devMode", "tdd"))
            th = choose_thresholds(s, c)
            return {
                "scenario": s.value,
                "complexity": c.value,
                "devMode": dm.value,
                "thresholds": explain_thresholds(th),
            }
        if name == "rules.ingest":
            return self._tool_rules_ingest(args)
        if name == "rules.validate":
            return self._tool_rules_validate()
        if name == "env.prepare":
            return self._tool_env_prepare(args)
        if name == "env.diagnose":
            return self._tool_env_diagnose()
        if name == "plan.suggest_next":
            return self._tool_plan_suggest_next()
        if name == "coverage.near":
            return self._tool_coverage_near(args)
        if name == "coverage.report":
            return self._tool_coverage_report(args)
        if name == "rules.maxima":
            return self._tool_rules_maxima()
        if name == "fs.apply_patch":
            # args: { files: [{path, content}] }
            files = args.get("files", [])
            run_checks = bool(args.get("runChecks", True))
            strict = bool(args.get("strict", False))
            dry_run = bool(args.get("dryRun", False))
            max_files = args.get("maxFiles", None)
            if isinstance(max_files, int) and max_files >= 0 and len(files) > max_files:
                raise ValueError("受控写入文件数超出限制（maxFiles）")
            changed_paths: List[Path] = []
            for f in files:
                content = f["content"]
                if run_checks and strict:
                    # 轻量严格检查：禁止 skip/xfail 标记
                    if "pytest.mark.skip" in content or "pytest.mark.xfail" in content:
                        raise ValueError(
                            "检测到 skip/xfail 标记，受控写入被拒绝（strict）。"
                        )
                    # 配置化禁用的内容片段（如 import pdb 等）
                    try:
                        ex_cfg2: Dict[str, Any] = (
                            self.cfg.get("execution", {})
                            if isinstance(self.cfg.get("execution", {}), dict)
                            else {}
                        )
                        patterns = ex_cfg2.get("disallow_patterns")
                        if isinstance(patterns, list) and patterns:
                            for pat in patterns:
                                if isinstance(pat, str) and pat and pat in content:
                                    raise ValueError("内容包含受限片段，受控写入被拒绝（strict）")
                    except Exception:
                        # 忽略解析错误，但在严格模式下仍保持 skip/xfail 拒绝
                        pass
                # 路径安全：禁止绝对路径与越权（必须在项目根内）
                if "path" not in f:
                    raise ValueError("缺少文件路径字段 'path'")
                p = Path(f["path"])
                if p.is_absolute():
                    raise ValueError("禁止写入绝对路径（必须为项目内相对路径）")
                root_res = self.project_root.resolve()
                dest = (root_res / p).resolve()
                try:
                    # 若越出项目根，将抛出 ValueError
                    dest.relative_to(root_res)
                except Exception:
                    raise ValueError("禁止写入项目根之外的路径（疑似路径穿越）")
                # 路径前缀白名单 / 扩展名白名单（可选）
                try:
                    ex_cfg: Dict[str, Any] = (
                        self.cfg.get("execution", {})
                        if isinstance(self.cfg.get("execution", {}), dict)
                        else {}
                    )
                    prefixes = ex_cfg.get("allowed_write_prefixes")
                    if isinstance(prefixes, list) and prefixes:
                        rel = str(dest.relative_to(root_res)).replace("\\", "/")
                        okp = any(str(prefix) and rel.startswith(str(prefix)) for prefix in prefixes)
                        if not okp:
                            raise ValueError("受控写入路径不在允许前缀清单内")
                    exts = ex_cfg.get("allowed_write_extensions")
                    if isinstance(exts, list) and exts:
                        ext = dest.suffix.lower()
                        if ext not in [str(e).lower() for e in exts if isinstance(e, str)]:
                            raise ValueError("受控写入文件扩展名不在允许清单内")
                except Exception as _e:
                    # 严格模式下升级为错误
                    if bool(ex_cfg.get("fs_guard_strict", False)):
                        raise
                if not dry_run:
                    self.fs.write_text(p, content)
                changed_paths.append(dest)
            result_checks: Dict[str, Any] = {"ok": True}
            if run_checks and not dry_run:
                do_type = bool(
                    self.cfg.get("performance", {})
                    .get("on_commit", {})
                    .get("typecheck_incremental", True)
                )
                result_checks = checks_mod.run_checks(
                    changed_paths,
                    cwd=self.project_root,
                    do_lint=True,
                    do_type=do_type,
                    do_quick_tests=True,
                )
                if strict and not result_checks.get("ok", True):
                    raise ValueError("受控写入后的检查未通过（lint/type/tests）")
            out: Dict[str, Any] = {
                "ok": True,
                "written": 0 if dry_run else len(files),
                "checks": result_checks,
            }
            if dry_run:
                out["would_write"] = [str(p) for p in changed_paths]
            return out
        if name == "git.install_hooks":
            return self._tool_git_install_hooks()
        if name == "nl.command":
            return self._tool_nl_command(args)
        if name == "plan.update":
            return self._tool_plan_update(args)
        if name == "plan.set":
            return self._tool_plan_set(args)
        if name == "config.get":
            return self._tool_config_get(args)
        if name == "config.update":
            return self._tool_config_update(args)
        if name == "ci.generate":
            return self._tool_ci_generate()
        if name == "ci.validate":
            return self._tool_ci_validate()
        if name == "ci.autofix":
            return self._tool_ci_autofix()
        if name == "rules.enforce":
            return self._tool_rules_enforce()
        raise ValueError(f"Unknown tool: {name}")

    # ---- resources/read helpers ----
    def _res_read_memory(self) -> Dict[str, Any]:
        """Read in-memory conversation snapshot as JSON resource.

        For uri variants:\n
        - memory://<id>/rollup → full snapshot (turns/summary/links)
        - memory://<id>/links → { links: [...] }
        """
        # We do not receive uri here directly in current call path; the caller
        # dispatches by startswith. Keep simple and always return full snapshot.
        snap = self.mm.snapshot()
        return {"mimeType": MIME_JSON, "text": json.dumps(snap, ensure_ascii=False)}

    # ---- tool helpers (extracted from _call_tool) ----
    def _tool_coverage_near(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Return coverage.near JSON using config defaults with arg overrides."""
        # Load defaults for near
        cfg_now = load_config(self.project_root)
        near_cfg = (
            (cfg_now.get("coverage", {}) or {}).get("near", {})
            if isinstance(cfg_now.get("coverage", {}), dict)
            else {}
        )
        within = float(args.get("within", near_cfg.get("within", 0.03)))
        top = int(args.get("top", near_cfg.get("top", 50)))
        min_module, policy = self._coverage_config_basics()
        return covsum.summarize_near(
            project_root=self.project_root,
            policy=policy,
            min_module=min_module,
            within=within,
            top=top,
        )

    def _tool_coverage_report(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Return coverage.report JSON combining weak/groups/near sections."""
        min_module, policy = self._coverage_config_basics()
        # near defaults
        cfg_now = load_config(self.project_root)
        near_cfg = (
            (cfg_now.get("coverage", {}) or {}).get("near", {})
            if isinstance(cfg_now.get("coverage", {}), dict)
            else {}
        )
        within = float(args.get("within", near_cfg.get("within", 0.03)))
        top = int(args.get("top", near_cfg.get("top", 50)))
        res_sum = covsum.summarize(
            project_root=self.project_root, policy=policy, min_module=min_module
        )
        res_grp = covsum.summarize_groups(
            project_root=self.project_root, policy=policy, min_module=min_module
        )
        res_near = covsum.summarize_near(
            project_root=self.project_root,
            policy=policy,
            min_module=min_module,
            within=within,
            top=top,
        )
        return {
            "ok": bool(
                res_sum.get("ok")
                and res_grp.get("ok", True)
                and res_near.get("ok", True)
            ),
            "weak": res_sum.get("weak", []),
            "groups": res_grp.get("groups", []),
            "near": res_near.get("near", []),
            "min_module": min_module,
        }

    def _tool_rules_maxima(self) -> Dict[str, Any]:
        """Return maxima from compiled rules JSON if present."""
        pjson = self.project_root / ri.COMPILED_JSON
        if not pjson.exists():
            return {"ok": False, "message": "compiled rules not found"}
        try:
            data = json.loads(pjson.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        meta = data.get("meta", {}) or {}
        maxima = (
            meta.get("maxima", {}) if isinstance(meta.get("maxima", {}), dict) else {}
        )
        return {"ok": True, "maxima": maxima}

    def _tool_git_install_hooks(self) -> Dict[str, Any]:
        paths = hooks_mod.install_git_hooks(self.project_root)
        return {"ok": True, "installed": paths}

    def _tool_nl_command(self, args: Dict[str, Any]) -> Dict[str, Any]:
        text = args.get("text", "")
        mapped = nl_mod.parse(text)
        return {"ok": True, "parsed": {"tool": mapped, "text": text}}

    def _tool_plan_update(self, args: Dict[str, Any]) -> Dict[str, Any]:
        text = args.get("text", "")
        if not text:
            raise ValueError("text required")
        progress_mod.write_plan(text, self.project_root)
        return {"ok": True}

    def _tool_plan_set(self, args: Dict[str, Any]) -> Dict[str, Any]:
        status = args.get("status")
        current = args.get("current")
        nxt = args.get("next")
        progress_mod.update_plan_fields(
            self.project_root, status=status, current=current, nxt=nxt
        )
        return {"ok": True}

    def _tool_env_prepare(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # 轻量实现：支持 dry-run 规划，或实际创建 venv 并可选安装基础工具
        py = str(args.get("python") or sys.executable)
        create = bool(args.get("create", True))
        install = bool(args.get("install", False))
        packages = list(
            args.get("packages")
            or [
                "ruff",
                "black",
                "isort",
                "mypy",
                "bandit",
                "pytest",
                "pytest-cov",
                "pre-commit",
            ]
        )
        venv_dir = self.project_root / ".mcp/venv"
        plan = {
            "python": py,
            "venv": str(venv_dir),
            "steps": [
                f"{py} -m venv {venv_dir}",
                f"{str(venv_dir / 'bin' / 'python' if os.name != 'nt' else venv_dir / 'Scripts' / 'python.exe')} -m pip install --upgrade pip",
                f"pip install {' '.join(packages)}",
            ],
        }
        if not create and not install:
            return {"ok": True, "dry": True, "plan": plan}
        created = False
        installed = False
        try:
            if create:
                venv_dir.parent.mkdir(parents=True, exist_ok=True)
                run_cmd(
                    [py, "-m", "venv", str(venv_dir)],
                    cwd=self.project_root,
                    check=False,
                )
                created = True
            if install:
                py_bin = (
                    venv_dir
                    / ("Scripts" if os.name == "nt" else "bin")
                    / ("python.exe" if os.name == "nt" else "python")
                )
                # upgrade pip then install selected packages
                run_cmd(
                    [str(py_bin), "-m", "pip", "install", "--upgrade", "pip"],
                    cwd=self.project_root,
                    check=False,
                )
                if packages:
                    run_cmd(
                        [str(py_bin), "-m", "pip", "install", *packages],
                        cwd=self.project_root,
                        check=False,
                    )
                installed = True
        except Exception as e:
            return {
                "ok": False,
                "message": f"env prepare failed: {e}",
                "plan": plan,
                "venv": str(venv_dir),
            }
        return {
            "ok": True,
            "created": created,
            "installed": installed,
            "venv": str(venv_dir),
            "plan": plan,
        }

    def _tool_plan_suggest_next(self) -> Dict[str, Any]:
        """Synthesize next steps based on memory summary and current plan."""
        snap = self.mm.snapshot()
        summary = str(snap.get("summary", ""))
        plan_text = progress_mod.read_plan(self.project_root)
        status, current, nxt = progress_mod.parse_plan(plan_text)
        next_steps: List[str] = []
        # Very light heuristic: prefer explicit '下一步/next' in plan else from summary
        if nxt:
            next_steps.append(nxt)
        else:
            for key in ("下一步", "next", "后续", "follow-up"):
                if key in summary:
                    # take the trailing 60 chars for display context
                    i = summary.find(key)
                    frag = summary[i : i + 60]
                    next_steps.append(frag)
                    break
        if not next_steps and current:
            next_steps.append(f"继续：{current}")
        handoff_plan = f"状态: {status or 'planned'}\n当前: {current or '-'}\n建议下一步: {next_steps[0] if next_steps else '-'}\n"
        return {
            "ok": True,
            "suggestions": {"next_steps": next_steps, "handoff_plan": handoff_plan},
        }

    # ---- rules tool helpers ----
    def _tool_rules_ingest(self, args: Dict[str, Any]) -> Dict[str, Any]:
        paths = args.get("paths", [])
        if not paths:
            raise ValueError("paths required")
        return ri.ingest(paths, project_root=self.project_root)

    def _tool_rules_validate(self) -> Dict[str, Any]:
        return ri.compile_rules(project_root=self.project_root)

    def _tool_rules_enforce(self) -> Dict[str, Any]:
        # 将已编译规则中的阈值/策略回写到项目配置，并返回门禁摘要
        compiled_path = self.project_root / ri.COMPILED_JSON
        if not compiled_path.exists():
            raise ValueError("compiled rules not found; run rules.ingest first")
        try:
            compiled = json.loads(compiled_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise ValueError(f"invalid compiled rules: {e}")
        policy = (
            compiled.get("policy", {})
            if isinstance(compiled.get("policy", {}), dict)
            else {}
        )
        pol_min_module = policy.get("coverage.min_module")
        pol_min_core = policy.get("coverage.min_core")
        cfg_path = self.project_root / DEFAULT_PROJECT_CONFIG_PATH
        ensure_project_config(cfg_path)
        try:
            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
        perf = (
            data.get("performance", {})
            if isinstance(data.get("performance", {}), dict)
            else {}
        )
        on_push = (
            perf.get("on_push", {}) if isinstance(perf.get("on_push", {}), dict) else {}
        )
        cov = (
            on_push.get("coverage", {})
            if isinstance(on_push.get("coverage", {}), dict)
            else {}
        )
        changed = False
        if isinstance(pol_min_module, (int, float)):
            cov["min_module"] = float(pol_min_module)
            changed = True
        if isinstance(pol_min_core, (int, float)):
            cov["min_core"] = float(pol_min_core)
            changed = True
        on_push["coverage"] = cov
        perf["on_push"] = on_push
        data["performance"] = perf
        # 同步 CI 相关策略：容器/安全扫描
        ci = data.get("ci", {}) if isinstance(data.get("ci", {}), dict) else {}
        ci_changed = False
        if bool(
            policy.get(POLICY_KEY_CONTAINER_REQUIRED)
            or policy.get(POLICY_KEY_CONTAINER_BASELINE)
        ) and not bool(ci.get("hadolint", False)):
            ci["hadolint"] = True
            ci_changed = True
        if bool(policy.get(POLICY_KEY_SECURITY_SAST_STRICT)) and not ci.get(
            "semgrep_config"
        ):
            ci["semgrep_config"] = "auto"
            ci_changed = True
        needs_hooks = False
        needs_ci_regen = False
        if ci_changed:
            data["ci"] = ci
            changed = True
            needs_ci_regen = True
        # hooks 需求：secrets_scan 或 container 基线策略
        if bool(policy.get(POLICY_KEY_SECURITY_SECRETS_SCAN)) or bool(
            policy.get(POLICY_KEY_CONTAINER_BASELINE)
        ):
            needs_hooks = True
        # 写回配置
        if changed:
            atomic_write_text(
                cfg_path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
            )
            self.cfg = load_config(self.project_root)
        # 生成门禁摘要
        enforced = []
        if "min_module" in cov:
            enforced.append(f"coverage.min_module={cov['min_module']}")
        if "min_core" in cov:
            enforced.append(f"coverage.min_core={cov['min_core']}")
        for k_src, tag in [
            ("test.no_skip_xfail", "no_skip_xfail"),
            ("test.warnings_as_errors", "warnings_as_errors"),
            (POLICY_KEY_SECURITY_SECRETS_SCAN, "secrets_scan"),
            (POLICY_KEY_SECURITY_SAST_STRICT, "sast_strict"),
            (POLICY_KEY_CONTAINER_REQUIRED, "container_required"),
            (POLICY_KEY_CONTAINER_BASELINE, "container_baseline"),
        ]:
            if bool(policy.get(k_src)):
                enforced.append(tag)
        if ci.get("hadolint"):
            enforced.append("ci.hadolint=true")
        if ci.get("semgrep_config"):
            enforced.append(f"ci.semgrep_config={ci.get('semgrep_config')}")
        return {
            "ok": True,
            "updated": {"coverage": cov, "ci": data.get("ci", {})},
            "changed": bool(changed),
            "enforced": enforced,
            "needs_hooks": needs_hooks,
            "needs_ci_regen": needs_ci_regen,
        }

    def _tool_env_diagnose(self) -> Dict[str, Any]:
        cfg_now = load_config(self.project_root)
        perf = (
            cfg_now.get("performance", {})
            if isinstance(cfg_now.get("performance", {}), dict)
            else {}
        )
        min_module = float(
            (perf.get("on_push", {}) or {}).get("coverage", {}).get("min_module", 0.9)
        )
        coverage_exists = (self.project_root / "coverage.xml").exists()
        compiled_json = self.project_root / ri.COMPILED_JSON
        compiled_exists = compiled_json.exists()
        maxima = {}
        if compiled_exists:
            try:
                data = json.loads(compiled_json.read_text(encoding="utf-8"))
                meta = data.get("meta", {}) or {}
                if isinstance(meta.get("maxima", {}), dict):
                    maxima = meta.get("maxima", {})
            except Exception:
                maxima = {}
        tools = {
            "python": sys.executable,
            "ruff": shutil.which("ruff") or "",
            "black": shutil.which("black") or "",
            "isort": shutil.which("isort") or "",
            "mypy": shutil.which("mypy") or "",
            "bandit": shutil.which("bandit") or "",
            "pytest": shutil.which("pytest") or "",
            "pre-commit": shutil.which("pre-commit") or "",
            "semgrep": shutil.which("semgrep") or "",
            "hadolint": shutil.which("hadolint") or "",
            "docker": shutil.which("docker") or "",
        }
        # 许可（演示校验）：存在性 + 占位签名/有效期检查
        try:
            from .license_utils import verify_license as _verify_license

            lic = _verify_license()
        except Exception:
            lic = {"ok": False, "activated": False}
        return {
            "ok": True,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "tools": tools,
            "config": {"min_module": min_module},
            "coverage": {"exists": coverage_exists},
            "rules": {"compiled_exists": compiled_exists},
            "maxima": maxima,
            "license": lic,
        }

    def _res_read_progress(self) -> Dict[str, Any]:
        """Read project plan markdown resource."""
        text = progress_mod.read_plan(self.project_root)
        return {"mimeType": MIME_MD, "text": text}

    def _res_read_config(self) -> Dict[str, Any]:
        """Read assistant.yaml as YAML resource (text only)."""
        cfg_file = self.project_root / DEFAULT_PROJECT_CONFIG_PATH
        text = cfg_file.read_text(encoding="utf-8") if cfg_file.exists() else ""
        return {"mimeType": MIME_YAML, "text": text}

    def _res_read_ci(self) -> Dict[str, Any]:
        """Read GitHub Actions CI workflow YAML if present."""
        ci_file = self.project_root / ".github/workflows/ci.yml"
        text = ci_file.read_text(encoding="utf-8") if ci_file.exists() else ""
        return {"mimeType": MIME_YAML, "text": text}

    # ---- CI tool helpers ----
    def _tool_ci_generate(self) -> Dict[str, Any]:
        ci_path = hooks_mod.generate_github_ci(self.project_root)
        return {"ok": True, "path": str(ci_path)}

    def _tool_ci_validate(self) -> Dict[str, Any]:
        ci_file = self.project_root / ".github/workflows/ci.yml"
        exists = ci_file.exists()
        content = ci_file.read_text(encoding="utf-8") if exists else ""
        checks = {
            "exists": exists,
            "has_precommit": "pre-commit run --all-files" in content,
            "has_hadolint": "hadolint" in content,
            "has_semgrep": "semgrep --error" in content,
            "has_tests": "pytest -q" in content,
            "has_bandit": "bandit -q" in content,
            "has_mutation": ("mutmut run" in content)
            or ("Mutation testing" in content),
            "has_node_tests": ("VS Code extension tests" in content)
            and ((self.project_root / "extensions/vscode/package.json").exists()),
            "has_python_matrix": "matrix:\n        python-version" in content
            or "matrix:\n      python-version" in content,
            "has_pip_cache": "cache: 'pip'" in content
            or 'cache: "pip"' in content
            or "cache: pip" in content,
            "has_npm_cache": "cache: 'npm'" in content
            or 'cache: "npm"' in content
            or "cache: npm" in content,
            "has_artifacts": "actions/upload-artifact@" in content,
            "has_junit": "--junitxml=" in content,
            "has_coverage_near": "coverage-near --within" in content,
            "has_near_artifact": "near.txt" in content,
            "has_combined_artifact": (
                "coverage.xml" in content
                and "pytest-junit.xml" in content
                and "near.txt" in content
            ),
            "has_combined_artifact_zip": "tests-artifacts.tar.gz" in content,
        }
        return {"ok": True, "checks": checks}

    def _tool_ci_autofix(self) -> Dict[str, Any]:
        res = hooks_mod.autofix_github_ci(self.project_root)
        return {"ok": True, **res}

    # ---- config tool helpers ----
    def _tool_config_get(self, args: Dict[str, Any]) -> Dict[str, Any]:
        cfg_path = self.project_root / DEFAULT_PROJECT_CONFIG_PATH
        ensure_project_config(cfg_path)
        try:
            raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception:
            raw = {}
        section = args.get("section")
        return {"ok": True, "config": raw.get(section, raw) if section else raw}

    def _tool_config_update(self, args: Dict[str, Any]) -> Dict[str, Any]:
        payload = args.get("data", {})
        if not isinstance(payload, dict):
            raise ValueError("data must be object")
        cfg_path = self.project_root / DEFAULT_PROJECT_CONFIG_PATH
        ensure_project_config(cfg_path)
        try:
            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
        ci = data.get("ci", {}) if isinstance(data.get("ci", {}), dict) else {}
        for k in ["hadolint", "hadolint_image", "hadolint_args", "semgrep_config"]:
            if k in payload:
                ci[k] = payload[k]
        data["ci"] = ci
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            cfg_path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
        )
        self.cfg = load_config(self.project_root)
        return {"ok": True, "ci": ci}

    def _res_read_coverage(self, uri: str) -> Dict[str, Any]:
        """Read coverage resources: summary/groups/tree/near/report as JSON."""
        min_module, policy = self._coverage_config_basics()
        if uri.endswith("/groups"):
            summary = covsum.summarize_groups(
                project_root=self.project_root, policy=policy, min_module=min_module
            )
            return {
                "mimeType": MIME_JSON,
                "text": json.dumps(summary, ensure_ascii=False),
            }
        if uri.endswith("/tree"):
            summary = covsum.summarize_tree(
                project_root=self.project_root, policy=policy, min_module=min_module
            )
            return {
                "mimeType": MIME_JSON,
                "text": json.dumps(summary, ensure_ascii=False),
            }
        if uri.endswith("/near"):
            within, top = self._coverage_near_defaults()
            summary = covsum.summarize_near(
                project_root=self.project_root,
                policy=policy,
                min_module=min_module,
                within=within,
                top=top,
            )
            return {
                "mimeType": MIME_JSON,
                "text": json.dumps(summary, ensure_ascii=False),
            }
        if uri.endswith("/report"):
            within, top = self._coverage_near_defaults()
            res_sum = covsum.summarize(
                project_root=self.project_root, policy=policy, min_module=min_module
            )
            res_grp = covsum.summarize_groups(
                project_root=self.project_root, policy=policy, min_module=min_module
            )
            res_near = covsum.summarize_near(
                project_root=self.project_root,
                policy=policy,
                min_module=min_module,
                within=within,
                top=top,
            )
            payload = {
                "ok": bool(
                    res_sum.get("ok")
                    and res_grp.get("ok", True)
                    and res_near.get("ok", True)
                ),
                "weak": res_sum.get("weak", []),
                "groups": res_grp.get("groups", []),
                "near": res_near.get("near", []),
                "min_module": min_module,
            }
            return {
                "mimeType": MIME_JSON,
                "text": json.dumps(payload, ensure_ascii=False),
            }
        summary = covsum.summarize(
            project_root=self.project_root, policy=policy, min_module=min_module
        )
        return {"mimeType": MIME_JSON, "text": json.dumps(summary, ensure_ascii=False)}

    def _coverage_config_basics(self) -> tuple[float, Any | None]:
        """Return (min_module, policy) from current config with safe defaults."""
        cfg_now = load_config(self.project_root)
        perf = (
            cfg_now.get("performance", {})
            if isinstance(cfg_now.get("performance", {}), dict)
            else {}
        )
        min_module = float(
            (perf.get("on_push", {}) or {}).get("coverage", {}).get("min_module", 0.9)
        )
        policy = (
            (cfg_now.get("coverage", {}) or {}).get("policy", None)
            if isinstance(cfg_now.get("coverage", {}), dict)
            else None
        )
        return min_module, policy

    def _coverage_near_defaults(self) -> tuple[float, int]:
        """Return default (within, top) for coverage.near from current config."""
        cfg_now2 = load_config(self.project_root)
        near_cfg = (
            (cfg_now2.get("coverage", {}) or {}).get("near", {})
            if isinstance(cfg_now2.get("coverage", {}), dict)
            else {}
        )
        within = float((near_cfg or {}).get("within", 0.03))
        top = int((near_cfg or {}).get("top", 50))
        return within, top

    def _res_read_rules(self, uri: str) -> Dict[str, Any]:
        """Read rules resources: compiled(.md/.json), suggestions, maxima."""
        if uri.endswith("/compiled"):
            path = self.project_root / ri.COMPILED_MD
            mime = MIME_MD
        elif uri.endswith("/compiled.json"):
            path = self.project_root / ri.COMPILED_JSON
            mime = MIME_JSON
        elif uri.endswith("/suggestions"):
            path = self.project_root / ri.SUGGESTIONS_MD
            mime = MIME_MD
        elif uri.endswith("/maxima"):
            pjson = self.project_root / ri.COMPILED_JSON
            if not pjson.exists():
                raise ValueError("rules resource not found; run rules.ingest first")
            try:
                data = json.loads(pjson.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            maxima = {}
            meta = data.get("meta", {}) or {}
            if isinstance(meta.get("maxima", {}), dict):
                maxima = meta.get("maxima", {})
            return {
                "mimeType": MIME_JSON,
                "text": json.dumps({"maxima": maxima}, ensure_ascii=False),
            }
        else:
            raise ValueError("unknown rules resource")
        if not path.exists():
            raise ValueError("rules resource not found; run rules.ingest first")
        return {"mimeType": mime, "text": path.read_text(encoding="utf-8")}

    def _project_id(self) -> str:
        return uuid.uuid5(uuid.NAMESPACE_URL, str(self.project_root.resolve())).hex[:8]

    def _tool_project_detect(self) -> Dict[str, Any]:
        root = self.project_root
        lang = None
        framework = None
        if (root / "pyproject.toml").exists() or list(root.glob("**/*.py")):
            lang = "python"
        elif (
            (root / "package.json").exists()
            or list(root.glob("**/*.ts"))
            or list(root.glob("**/*.js"))
        ):
            lang = "node"
        elif (root / "Cargo.toml").exists():
            lang = "rust"
        else:
            lang = "unknown"
        return {"language": lang, "framework": framework, "root": str(root)}


def serve_stdio() -> None:
    # 行分割的 JSON-RPC：每行一个 JSON 对象
    server = JsonRpcServer()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            }
            print(json.dumps(resp, ensure_ascii=False), flush=True)
            continue
        response = server.handle(request)
        print(json.dumps(response, ensure_ascii=False), flush=True)


# Small subprocess wrapper for consistency with dev_agent/hooks
# 使用共享 run_cmd（原本模块内的 _run_cmd 已移除）
