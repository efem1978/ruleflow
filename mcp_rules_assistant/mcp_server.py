from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

import yaml

from . import __version__ as PKG_VERSION
from . import checks as checks_mod
from . import coverage_summary as covsum
from . import hooks as hooks_mod
from . import nl as nl_mod
from . import progress as progress_mod
from . import rules_ingest as ri
from .config import DEFAULT_PROJECT_CONFIG_PATH, ensure_project_config, load_config
from .fs_wrapper import FSGuard, atomic_write_text
from .license_utils import verify_license as _verify_license
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
    """轻量 JSON-RPC 2.0 stdio 服务器（MCP 风格方法名）。

    说明：已具备生产所需的关键门禁与资源/工具接口；并发/流控保持简化。
    """

    def __init__(self) -> None:
        setup_default_tools()
        self.project_root = Path.cwd()
        self._mem_ns: str | None = None
        self.mm = MemoryManager(self.project_root)
        self.fs = FSGuard(self.project_root)
        self.settings: Dict[str, Any] = {"memory_auto": False}
        self.cfg = load_config(self.project_root)
        self._cfg_root = self.project_root
        # very light rate limiter (per-process): window 1s
        self._rl_window_start: float = 0.0
        self._rl_count: int = 0

    # ---- small internal helpers (testability without behavior change) ----
    def _get_exec_flag(self, key: str, default: Any) -> Any:
        """Fetch an execution flag from config.

        Separated for testability so edge branches can be exercised by
        monkeypatching this helper in unit tests without altering runtime behavior.
        """
        try:
            ex_cfg = (
                self.cfg.get("execution", {})
                if isinstance(self.cfg.get("execution", {}), dict)
                else {}
            )
            return (ex_cfg or {}).get(key, default)
        except Exception:
            return default

    def _license_required(self) -> bool:
        try:
            # 若项目根变化，重新加载；否则优先尊重内存中的显式注入（测试用）
            if getattr(self, "_cfg_root", None) != self.project_root:
                cfg_src = load_config(self.project_root)
                self.cfg = cfg_src
                self._cfg_root = self.project_root
            else:
                cfg_src = self.cfg
            lic_cfg = (
                cfg_src.get("license", {})
                if isinstance(cfg_src.get("license", {}), dict)
                else {}
            )
            return bool(lic_cfg.get("required", False))
        except Exception as e:
            # 保持默认回退为 False，仅记录调试信息
            try:
                import logging  # pragma: no cover

                logging.getLogger(__name__).debug(
                    "[mcp] license.required parse failed: %r", e
                )  # pragma: no cover
            except Exception:  # pragma: no cover
                pass
            return False

    def _ensure_license(self) -> None:
        if not self._license_required():
            return
        res = {}
        try:
            res = _verify_license()
        except Exception as e:
            # 许可校验失败路径：仅记录调试信息，不泄露具体异常
            try:
                import logging  # pragma: no cover

                logging.getLogger(__name__).debug(
                    "[mcp] license verify exception: %r", e
                )  # pragma: no cover
            except Exception:  # pragma: no cover
                pass
            res = {"ok": False}
        if not bool(res.get("ok")):
            raise ValueError("license required or invalid")

    # ---- MCP-like methods ----
    def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})
        result: Dict[str, Any] = {}
        try:
            # --- light limits (size & rate) ---
            try:
                exec_cfg: Dict[str, Any] = (
                    self.cfg.get("execution", {})
                    if isinstance(self.cfg.get("execution", {}), dict)
                    else {}
                )
                max_bytes = int(exec_cfg.get("max_request_bytes", 256 * 1024))
            except Exception as e:
                max_bytes = 256 * 1024
                try:
                    import logging  # pragma: no cover

                    logging.getLogger(__name__).debug(
                        "[mcp] exec.max_request_bytes parse: %r", e
                    )  # pragma: no cover
                except Exception:  # pragma: no cover
                    pass
            try:
                rps = int(exec_cfg.get("rate_limit_rps", 20))  # type: ignore[name-defined]
            except Exception:  # pragma: no cover - defensive
                rps = 20
            try:
                sz = len(json.dumps(params, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                sz = 0
                try:
                    import logging  # pragma: no cover

                    logging.getLogger(__name__).debug(
                        "[mcp] request size calc failed: %r", e
                    )  # pragma: no cover
                except Exception:  # pragma: no cover
                    pass
            if max_bytes >= 0 and sz > max_bytes:
                raise ValueError("request too large")
            now = time.monotonic()
            if now - self._rl_window_start >= 1.0:
                self._rl_window_start = now
                self._rl_count = 0
            self._rl_count += 1
            if rps >= 0 and self._rl_count > rps:
                raise ValueError("rate limit exceeded")
            # --- normal dispatch ---
            if method == "initialize":
                # 声明最小能力集，含 prompts（提供占位端点）
                caps: Dict[str, Any] = {
                    "tools": True,
                    "resources": True,
                    "prompts": True,
                }
                result = {
                    "server": "mcp-rules-assistant",
                    "version": str(PKG_VERSION),
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
                # 附加命名空间 memory 资源：memory.<ns>.json → memory://<id>/rollup?ns=<ns>
                try:
                    for p in (self.project_root / ".mcp").glob("memory.*.json"):
                        ns = p.name.replace("memory.", "").replace(".json", "")
                        if ns:
                            resources_list.insert(
                                1,
                                {
                                    "uri": f"memory://{self._project_id()}/rollup?ns={ns}",
                                    "name": f"Last 20 turns & summary ({ns})",
                                },
                            )
                except Exception:
                    pass
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
                        result = self._res_read_memory(uri)
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
                # 可选启用：当环境变量 MCP_PROMPTS_ENABLE=1 或配置 prompts.enabled 为 true 时返回最小内置模板
                if self._prompts_enabled():
                    result = {
                        "prompts": [
                            {
                                "name": "handoff.next_steps",
                                "description": "Summarize current status and suggest next steps",
                            },
                            {
                                "name": "rules.summary",
                                "description": "Summarize compiled rules and gates for handoff",
                            },
                        ]
                    }
                else:
                    result = {"prompts": []}
            elif method == "prompts/get":
                name = str(params.get("name", ""))
                if not self._prompts_enabled():
                    result = {"ok": False, "message": f"prompt '{name}' not found"}
                else:
                    tpl = self._prompt_template(name)
                    result = (
                        tpl
                        if tpl
                        else {"ok": False, "message": f"prompt '{name}' not found"}
                    )
            else:
                # JSON-RPC: method not found
                raise KeyError("method_not_found")
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except (
            Exception
        ) as e:  # noqa: BLE001 - boundary mapping to JSON-RPC error codes
            msg = str(e)
            code = -32603  # internal error (default)
            # 粗粒度分类（最小必要）：
            if isinstance(e, KeyError):
                # KeyError.__str__ 会把键名包上引号，使用 args 更稳妥
                key = e.args[0] if getattr(e, "args", ()) else ""
                if key == "method_not_found":
                    code = -32601
                    msg = "method not found"
            elif isinstance(e, ValueError):
                # "Unknown resource uri" 历史约定使用 -32000（兼容既有测试）
                if msg == "Unknown resource uri":
                    code = -32000
                else:
                    code = -32602  # invalid params / semantic validation
            elif isinstance(e, FileNotFoundError):
                code = -32001  # custom: resource not found
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": code, "message": msg},
            }

    # ---- Tools implementations ----
    def _call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        # 许可门禁：对敏感工具启用软硬门禁（受配置 license.required 控制）
        gated = {
            "rules.enforce",
            "rules.onboard",
            "ci.generate",
            "ci.validate",
            "ci.autofix",
            "git.install_hooks",
        }
        try:
            if name in gated:
                # 对 ci.validate 提供更友好的摘要输出
                if name == "ci.validate" and self._license_required():
                    ok = False
                    try:
                        res = _verify_license()
                        ok = bool(res.get("ok"))
                    except Exception:
                        ok = False
                    if not ok:
                        # 写出摘要，供 CI/人工审阅
                        dash = self.project_root / ".mcp" / "dashboard"
                        dash.mkdir(parents=True, exist_ok=True)
                        (dash / "release_check.md").write_text(
                            "License required or invalid — ci.validate gated\n",
                            encoding="utf-8",
                        )
                        # 仍按硬门禁阻断
                        raise ValueError("license required or invalid")
                # 其他 gated 正常校验
                self._ensure_license()
        except Exception:
            # 保守：直接抛出以阻断敏感调用
            raise
        if name == "project.detect":
            return self._tool_project_detect()
        if name == "project.switch":
            # arguments: { path?: string }
            new_path = args.get("path")
            if new_path:
                p = Path(new_path).expanduser().resolve()
                old_root = self.project_root
                # 在旧项目记忆中记录“切换到”链接
                try:
                    self.mm.add_link(p.name or str(p), "switched_to", str(p))
                except Exception as e:
                    import logging

                    logging.getLogger(__name__).debug(
                        "[mcp] add_link switched_to failed: %r", e
                    )
                # 切换项目根
                self.project_root = p
                # Rebind per-project helpers
                self.mm = MemoryManager(self.project_root)
                self.fs = FSGuard(self.project_root)
                self.cfg = load_config(self.project_root)
                # 在新项目记忆中记录“来自”链接
                try:
                    self.mm.add_link(
                        old_root.name if hasattr(old_root, "name") else str(old_root),
                        "switched_from",
                        str(old_root),
                    )
                except Exception as e:
                    import logging

                    logging.getLogger(__name__).debug(
                        "[mcp] add_link switched_from failed: %r", e
                    )
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
            ns = args.get("project") or args.get("scope")
            ns_str = str(ns).strip() if isinstance(ns, str) else ""
            # 绑定命名空间（可选）：.mcp/memory.<ns>.json
            if ns_str:
                safe_ns = "".join(ch for ch in ns_str if ch.isalnum() or ch in "_-.")
                if not safe_ns:
                    raise ValueError("invalid memory namespace")
                self._mem_ns = safe_ns
                f = self.project_root / ".mcp" / f"memory.{safe_ns}.json"
                self.mm = MemoryManager(self.project_root, file_override=f)
            self.settings["memory_auto"] = on
            return {"ok": True, "auto": on, "namespace": self._mem_ns or "default"}
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
        if name == "rules.onboard":
            return self._tool_rules_onboard(args)
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
        if name == "coverage.export":
            return self._tool_coverage_export(args)
        if name == "rules.maxima":
            return self._tool_rules_maxima()
        if name == "ide.scaffold":
            return self._tool_ide_scaffold(args)
        if name == "compliance.commitment":
            return self._tool_compliance_commitment(args)
        if name == "fs.apply_patch":
            # args: { files: [{path, content}] }
            files = args.get("files", [])
            if not isinstance(files, list):
                raise ValueError("参数错误：files 必须为数组")
            run_checks = bool(args.get("runChecks", True))
            strict = bool(args.get("strict", False))
            dry_run = bool(args.get("dryRun", False))
            # 有效文件数上限：优先参数，其次配置 execution.max_files，默认 100
            max_files = args.get("maxFiles", None)
            exec_cfg_eff: Dict[str, Any] = (
                self.cfg.get("execution", {})
                if isinstance(self.cfg.get("execution", {}), dict)
                else {}
            )
            # 只读模式：阻断任何写入（dry_run 允许查询 would_write 列表）
            if bool(exec_cfg_eff.get("readonly", False)) and not bool(dry_run):
                raise ValueError("受控写入被拒绝：只读模式已启用（execution.readonly）")
            if not isinstance(max_files, int):
                max_files = int(exec_cfg_eff.get("max_files", 100))
            if isinstance(max_files, int) and max_files >= 0 and len(files) > max_files:
                raise ValueError("受控写入文件数超出限制（maxFiles）")
            changed_paths: List[Path] = []
            pattern_hit_any = False
            for f in files:
                if not isinstance(f, dict):
                    raise ValueError("参数错误：files[*] 必须为对象")
                content = f["content"]
                if not isinstance(content, str):
                    raise ValueError("参数错误：content 必须为字符串")
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
                            # 仅记录/旁路：按当前约定，disallow_patterns 命中不在此处阻断
                            # （仅 skip/xfail 属于严格阻断）；保持与测试与文档一致的“软拦截”语义。
                            pattern_hit = any(
                                isinstance(pat, str) and pat and pat in content
                                for pat in patterns
                            )
                            if pattern_hit:
                                pattern_hit_any = True
                                # 受控日志：设置 MCP_FS_LOG=1 时输出命中摘要（默认不输出）
                                if os.environ.get("MCP_FS_LOG", "0") in (
                                    "1",
                                    "true",
                                    "True",
                                ):
                                    logging.getLogger("mcp.fs").info(
                                        "[fs.apply_patch] disallow_patterns hit (soft): path=%s",
                                        f.get("path", ""),
                                    )
                                # 可选硬门禁：当 execution.disallow_patterns_hard 为真时直接拒绝
                                try:
                                    hard_gate = bool(
                                        self._get_exec_flag(
                                            "disallow_patterns_hard", False
                                        )
                                    )
                                except Exception:
                                    hard_gate = False
                                if hard_gate:
                                    raise ValueError(
                                        "检测到受禁内容片段，按配置 execution.disallow_patterns_hard 拒绝写入"
                                    )
                    except Exception as e:
                        # 忽略解析错误，但在严格模式下仍保持 skip/xfail 拒绝
                        import logging

                        logging.getLogger(__name__).debug(
                            "[mcp] disallow_patterns parse skipped: %r", e
                        )
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
                # 禁止写入符号链接
                if dest.exists() and dest.is_symlink():
                    raise ValueError("禁止写入符号链接目标文件")
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
                        okp = any(
                            str(prefix) and rel.startswith(str(prefix))
                            for prefix in prefixes
                        )
                        if not okp:
                            raise ValueError("受控写入路径不在允许前缀清单内")
                    exts = ex_cfg.get("allowed_write_extensions")
                    if isinstance(exts, list) and exts:
                        ext = dest.suffix.lower()
                        if ext not in [
                            str(e).lower() for e in exts if isinstance(e, str)
                        ]:
                            raise ValueError("受控写入文件扩展名不在允许清单内")
                except Exception as _e:
                    # 严格模式下升级为错误（使用外层设置），解析异常时降级为 False
                    try:
                        strict_on = bool(self._get_exec_flag("fs_guard_strict", False))
                    except Exception as e:
                        import logging

                        logging.getLogger(__name__).debug(
                            "[mcp] exec_cfg strict flag parse: %r", e
                        )
                        strict_on = False
                    if strict_on:
                        raise
                # 内容大小限制：默认 512KB，可通过 execution.max_content_bytes 调整
                try:
                    max_bytes = int(exec_cfg_eff.get("max_content_bytes", 512 * 1024))
                except Exception:
                    max_bytes = 512 * 1024
                if max_bytes >= 0 and len(content.encode("utf-8")) > max_bytes:
                    raise ValueError("受控写入内容超出大小限制")
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
                if strict and not result_checks.get("ok", True) and not pattern_hit_any:
                    raise ValueError(
                        "受控写入后的检查未通过（lint/type/tests）。"
                        "可在 .mcp/assistant.yaml 中调整 execution.fs_guard_post_checks / fs_guard_strict。"
                    )
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
        if name == "license.activate":
            return self._tool_license_activate(args)
        if name == "license.verify":
            return self._tool_license_verify()
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
    def _res_read_memory(self, uri: str | None = None) -> Dict[str, Any]:
        """Read in-memory conversation snapshot as JSON resource.

        For uri variants:\n
        - memory://<id>/rollup → full snapshot (turns/summary/links)
        - memory://<id>/rollup?ns=<ns> → snapshot of namespaced memory file
        - memory://<id>/links → { links: [...] }
        """
        # 可选解析命名空间参数
        ns = None
        try:
            u = str(uri or "")
            if "?ns=" in u:
                ns = u.split("?ns=", 1)[1].strip()
        except Exception:
            ns = None
        if ns:
            p = self.project_root / ".mcp" / f"memory.{ns}.json"
            if not p.exists():
                raise FileNotFoundError("memory namespace not found")
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                data = {"turns": [], "summary": "", "links": []}
            return {"mimeType": MIME_JSON, "text": json.dumps(data, ensure_ascii=False)}
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

    def _tool_coverage_export(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Export coverage summary and CSVs to .mcp/dashboard (or provided dir).

        Args:
          outDir: optional output directory (default .mcp/dashboard)
          weakTop: optional int (default 20)
          nearTop: optional int (default from config coverage.near.top, fallback 50)
          within: optional float (0..1, default from config coverage.near.within)
        """
        import csv as _csv
        import json as _json
        from pathlib import Path as _P

        out_dir = args.get("outDir") or str(self.project_root / ".mcp" / "dashboard")
        weak_top = int(args.get("weakTop", 20))
        # near defaults
        cfg_now = load_config(self.project_root)
        near_cfg = (
            (cfg_now.get("coverage", {}) or {}).get("near", {})
            if isinstance(cfg_now.get("coverage", {}), dict)
            else {}
        )
        within = float(args.get("within", near_cfg.get("within", 0.03)))
        near_top = int(args.get("nearTop", near_cfg.get("top", 50)))
        outp = _P(out_dir)
        outp.mkdir(parents=True, exist_ok=True)

        min_module, policy = self._coverage_config_basics()
        res_sum = covsum.summarize(
            project_root=self.project_root, policy=policy, min_module=min_module
        )
        if not res_sum.get("ok"):
            return {
                "ok": False,
                "message": res_sum.get("message", "coverage.xml missing"),
            }
        res_grp = covsum.summarize_groups(
            project_root=self.project_root, policy=policy, min_module=min_module
        )
        res_near = covsum.summarize_near(
            project_root=self.project_root,
            policy=policy,
            min_module=min_module,
            within=within,
            top=near_top,
        )

        payload = {
            "weak": res_sum.get("weak", []) or [],
            "groups": res_grp.get("groups", []) or [],
            "near": res_near.get("near", []) or [],
            "min_module": min_module,
        }
        (outp / "coverage_summary.json").write_text(
            _json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        weak_list = list(payload["weak"]) if isinstance(payload["weak"], list) else []
        for it in weak_list:
            try:
                it["delta"] = float(it.get("threshold", 0.0)) - float(
                    it.get("coverage", 0.0)
                )
            except Exception:
                it["delta"] = 0.0
        weak_sorted = sorted(
            weak_list, key=lambda x: x.get("delta", 0.0), reverse=True
        )[:weak_top]
        with (outp / "weak_top.csv").open("w", newline="", encoding="utf-8") as f:
            w = _csv.writer(f)
            w.writerow(["file", "coverage", "threshold", "delta"])
            for it in weak_sorted:
                w.writerow(
                    [
                        it.get("file", ""),
                        float(it.get("coverage", 0.0)),
                        float(it.get("threshold", 0.0)),
                        float(it.get("delta", 0.0)),
                    ]
                )
        near_list = list(payload["near"]) if isinstance(payload["near"], list) else []
        with (outp / "near_top.csv").open("w", newline="", encoding="utf-8") as f:
            w = _csv.writer(f)
            w.writerow(["file", "coverage", "threshold", "delta_up"])
            for it in near_list[:near_top]:
                w.writerow(
                    [
                        it.get("file", ""),
                        float(it.get("coverage", 0.0)),
                        float(it.get("threshold", 0.0)),
                        float(it.get("delta_up", 0.0)),
                    ]
                )
        groups_list = (
            list(payload["groups"]) if isinstance(payload["groups"], list) else []
        )
        with (outp / "groups.csv").open("w", newline="", encoding="utf-8") as f:
            w = _csv.writer(f)
            w.writerow(["prefix", "coverage", "threshold", "weak_count", "files_count"])
            for g in groups_list:
                w.writerow(
                    [
                        g.get("prefix", ""),
                        float(g.get("coverage", 0.0)),
                        float(g.get("threshold", 0.0)),
                        int(g.get("weak_count", 0)),
                        int(g.get("files_count", 0)),
                    ]
                )
        return {
            "ok": True,
            "out_dir": str(outp),
            "files": [
                str(outp / "coverage_summary.json"),
                str(outp / "weak_top.csv"),
                str(outp / "near_top.csv"),
                str(outp / "groups.csv"),
            ],
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
        for k, v in (("status", status), ("current", current), ("next", nxt)):
            if v is not None and not isinstance(v, str):
                raise ValueError(f"{k} must be string when provided")
        progress_mod.update_plan_fields(
            self.project_root, status=status, current=current, nxt=nxt
        )
        return {"ok": True}

    def _tool_env_prepare(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # 轻量实现：支持 dry-run 规划，或实际创建 venv 并可选安装基础工具
        py = str(args.get("python") or sys.executable)
        create = bool(args.get("create", True))
        install = bool(args.get("install", False))
        pk_arg = args.get("packages")
        if pk_arg is None:
            packages = [
                "ruff",
                "black",
                "isort",
                "mypy",
                "bandit",
                "pytest",
                "pytest-cov",
                "pre-commit",
            ]
        else:
            if not isinstance(pk_arg, list) or not all(
                isinstance(x, str) for x in pk_arg
            ):
                raise ValueError("packages must be a list of strings")
            packages = list(pk_arg)
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

    def _tool_license_activate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Copy provided license JSON file to ~/.mcp/license.json (best-effort)."""
        src = Path(str(args.get("path", "")).strip()).expanduser().resolve()
        if not src.exists():
            raise ValueError("license file not found")
        dst = Path.home() / ".mcp" / "license.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(src), str(dst))
        # refresh config not needed; diagnose reads from disk
        return {"ok": True, "path": str(dst)}

    def _tool_license_verify(self) -> Dict[str, Any]:
        """Verify local license (if present) and return status JSON."""
        try:
            lic = _verify_license()
        except Exception as e:
            return {"ok": False, "message": str(e)}
        return {"ok": True, "license": lic}

    # ---- rules tool helpers ----
    def _tool_rules_ingest(self, args: Dict[str, Any]) -> Dict[str, Any]:
        paths = args.get("paths", [])
        if not isinstance(paths, list) or not paths:
            raise ValueError("paths required (list of files/dirs)")
        for p in paths:
            if not isinstance(p, str) or not p.strip():
                raise ValueError("paths must contain non-empty strings")
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

    def _tool_rules_onboard(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Onboarding wizard (non-interactive via args) to choose and apply a rules profile.

        Args (optional): scenario, complexity, devMode, apply(bool)
        Behavior: if values missing, use simple heuristics (language/files count) to default.
        When apply=True, write thresholds to `.mcp/assistant.yaml` (min_module, mutation_test flag).
        """
        # defaults via detection
        try:
            det = self._tool_project_detect()
            lang = str(det.get("language", "python"))
        except Exception:
            lang = "python"
        scenario = str(args.get("scenario") or "personal")
        complexity = str(args.get("complexity") or "small")
        dev_mode = str(args.get("devMode") or "tdd")
        # rough project size heuristic
        try:
            py_files = list(self.project_root.rglob("*.py"))
            tests = (
                list((self.project_root / "tests").rglob("test_*.py"))
                if (self.project_root / "tests").exists()
                else []
            )
            n = len(py_files)
            if not args.get("complexity"):
                if n > 800 or len(tests) > 300:
                    complexity = "large"
                elif n > 200 or len(tests) > 80:
                    complexity = "medium"
                else:
                    complexity = "small"
        except Exception as e:
            import logging

            logging.getLogger(__name__).debug(
                "[mcp] project size heuristic failed: %r", e
            )
        from .rules import Complexity, Scenario, choose_thresholds, explain_thresholds

        try:
            th = choose_thresholds(Scenario(scenario), Complexity(complexity))
        except Exception:
            th = choose_thresholds(Scenario.PERSONAL, Complexity.SMALL)
        apply = bool(args.get("apply", True))
        applied = False
        if apply:
            cfg_path = (
                self.project_root / DEFAULT_PROJECT_CONFIG_PATH
                if not DEFAULT_PROJECT_CONFIG_PATH.is_absolute()
                else DEFAULT_PROJECT_CONFIG_PATH
            )
            ensure_project_config(cfg_path)
            # load, merge, write
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
                perf.get("on_push", {})
                if isinstance(perf.get("on_push", {}), dict)
                else {}
            )
            cov = (
                on_push.get("coverage", {})
                if isinstance(on_push.get("coverage", {}), dict)
                else {}
            )
            cov["min_module"] = float(th.coverage_min_module)
            on_push["coverage"] = cov
            on_push["mutation_test"] = bool(th.mutation_required)
            perf["on_push"] = on_push
            data["performance"] = perf
            try:
                cfg_path.write_text(
                    yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
                )
                self.cfg = load_config(self.project_root)
                applied = True
            except Exception:
                applied = False
        return {
            "ok": True,
            "language": lang,
            "scenario": scenario,
            "complexity": complexity,
            "devMode": dev_mode,
            "thresholds": explain_thresholds(th),
            "applied": applied,
        }

    def _tool_ide_scaffold(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Generate per-IDE integration scaffold under .mcp/ide/<editor>.

        Supported editors: vscode, cursor, jetbrains, neovim
        """
        editor = str(args.get("editor", "vscode")).strip().lower()
        base = self.project_root / ".mcp/ide" / editor
        base.mkdir(parents=True, exist_ok=True)
        files: list[str] = []
        if editor in ("vscode", "cursor"):
            # VS Code/Cursor share same engine; provide settings sample and README
            sample = {
                "copilot.mcp.tools": {
                    "ruleflow": {
                        "command": "python3",
                        "args": ["-m", "mcp_rules_assistant.cli", "start"],
                        "cwd": "${workspaceFolder}",
                        "env": {"PYTHONUNBUFFERED": "1"},
                    }
                }
            }
            import json as _json

            (base / "settings.sample.json").write_text(
                _json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (base / "README.md").write_text(
                "VS Code/Cursor: 将 settings.sample.json 合并至工作区 .vscode/settings.json；在命令面板执行 ‘RuleFlow: Open Panel’ 或 Copilot MCP 面板中选择 ruleflow。\n",
                encoding="utf-8",
            )
            files.extend(
                [
                    str((base / "settings.sample.json").relative_to(self.project_root)),
                    str((base / "README.md").relative_to(self.project_root)),
                ]
            )
        elif editor == "jetbrains":
            # Provide External Tools XML sample + README
            xml = (
                (
                    """
<externalTools>
  <tool name="RuleFlow MCP Server">
    <exec>%(python)s</exec>
    <arguments>-m mcp_rules_assistant.cli start</arguments>
    <working_dir>$ProjectFileDir$</working_dir>
  </tool>
</externalTools>
"""
                ).strip()
                % {"python": "python3"}
            )
            (base / "externalTools.sample.xml").write_text(xml, encoding="utf-8")
            (base / "README.md").write_text(
                "JetBrains: Settings → Tools → External Tools → Import 外部工具，或手工添加以上命令以启动 MCP 服务器；通过 Terminal 或自定义动作触发 ruleflow CLI 命令。\n",
                encoding="utf-8",
            )
            files.extend(
                [
                    str(
                        (base / "externalTools.sample.xml").relative_to(
                            self.project_root
                        )
                    ),
                    str((base / "README.md").relative_to(self.project_root)),
                ]
            )
        elif editor == "neovim":
            # Provide minimal vimscript & lua snippet + README
            (base / "init.sample.vim").write_text(
                ":command! RuleFlowStart :terminal python3 -m mcp_rules_assistant.cli start\n",
                encoding="utf-8",
            )
            (base / "init.sample.lua").write_text(
                (
                    "local function RuleFlowStart()\n"
                    "  vim.fn.termopen({'python3','-m','mcp_rules_assistant.cli','start'})\n"
                    "end\n"
                    "vim.api.nvim_create_user_command('RuleFlowStart', RuleFlowStart, {})\n"
                ),
                encoding="utf-8",
            )
            (base / "README.md").write_text(
                (
                    "Neovim:\n"
                    "- Vimscript: 在 init.vim 引入 init.sample.vim，使用 :RuleFlowStart 启动 MCP 服务器\n"
                    "- Lua: 在 init.lua 引入 init.sample.lua（或复制函数体），同样使用 :RuleFlowStart\n"
                    "- 可通过 :terminal 执行 CLI 子命令（如 rules/coverage/ci）\n"
                ),
                encoding="utf-8",
            )
            files.extend(
                [
                    str((base / "init.sample.vim").relative_to(self.project_root)),
                    str((base / "init.sample.lua").relative_to(self.project_root)),
                    str((base / "README.md").relative_to(self.project_root)),
                ]
            )
        else:
            raise ValueError("unsupported editor (vscode/cursor/jetbrains/neovim)")
        return {"ok": True, "editor": editor, "files": files}

    def _tool_compliance_commitment(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Return standard AI compliance commitment and optionally write to .mcp/compliance.md."""
        text = (
            """
# AI 合规承诺 / AI Compliance Commitment

- 严格遵循 TDD：先红后绿再重构；禁止跳过或投机（no skip/xfail）。
- 警告视为错误（-W error），覆盖率达标（核心≥98%，其余≥95%）；不得以拆分测试等方式规避整体质量。
- 变更伴随测试与文档；不得降低门槛；遵守计划顺序（禁止跳跃）。
- 不引入未经批准的依赖；不暴露端口/遥测；仅落盘状态文件。
- 发现冲突/冗余/不一致，先最小化、再统一，遵循奥卡姆剃刀原则。

English summary:
- TDD strictly; no skip/xfail; warnings-as-errors; coverage thresholds enforced.
- Changes include tests and docs; follow plan order; no scope jumping.
- No unapproved deps; no ports/telemetry; local file artifacts only.
- Resolve conflicts and duplication with minimal and consistent outcome (Occam's razor).
"""
        ).strip()
        write = bool(args.get("write", True))
        path = self.project_root / ".mcp/compliance.md"
        if write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return {"ok": True, "written": write, "path": str(path), "text": text}

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
        # 许可校验：存在性 + 签名/有效期检查（hs256/rs256/ed25519）
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
        """Update assistant.yaml configuration.

        Compatibility:
        - Preferred: { data: { ci:..., execution:.../flags... } }
        - Also accepts flattened top-level keys (no `data` wrapper), e.g.:
          { mutation_gate_strict: true, execution: { checks_delegate_run_cmd: true } }
        """
        payload = args.get("data", None)
        # 兼容平铺参数：当未提供 data 时，将整个 args 视为负载
        if payload is None:
            payload = dict(args)
        if not isinstance(payload, dict):
            raise ValueError("data must be object or provide flattened keys")
        # 许可硬门禁：当修改 CI 关键项且 license.required=true 时，需先通过许可校验
        try:
            touched: set[str] = set()
            pf = payload
            for k in (
                "hadolint",
                "hadolint_image",
                "hadolint_args",
                "semgrep_config",
                "mutation_gate_strict",
                "vscode_required",
            ):
                if k in pf:
                    touched.add(k)
            if isinstance(pf.get("ci"), dict):
                for k in pf["ci"].keys():
                    if k in {
                        "hadolint",
                        "hadolint_image",
                        "hadolint_args",
                        "semgrep_config",
                        "mutation_gate_strict",
                        "vscode_required",
                    }:
                        touched.add(k)
            if touched and self._license_required():
                self._ensure_license()
        except Exception:
            # 容错：解析失败不阻断（具体 CI 工具调用仍受门禁保护）
            pass
        cfg_path = self.project_root / DEFAULT_PROJECT_CONFIG_PATH
        ensure_project_config(cfg_path)
        try:
            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
        ci = data.get("ci", {}) if isinstance(data.get("ci", {}), dict) else {}
        for k in [
            "hadolint",
            "hadolint_image",
            "hadolint_args",
            "semgrep_config",
            "mutation_gate_strict",
            "vscode_required",
        ]:
            if k in payload:
                ci[k] = payload[k]
        data["ci"] = ci
        # Optional: update execution.checks_delegate_run_cmd
        if "execution" in payload and isinstance(payload["execution"], dict):
            ex = (
                data.get("execution", {})
                if isinstance(data.get("execution", {}), dict)
                else {}
            )
            if "checks_delegate_run_cmd" in payload["execution"]:
                ex["checks_delegate_run_cmd"] = bool(payload["execution"]["checks_delegate_run_cmd"])  # type: ignore[truthy-bool]
            data["execution"] = ex
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

    # ---- prompts helpers ----
    def _prompts_enabled(self) -> bool:
        try:
            if str(os.environ.get("MCP_PROMPTS_ENABLE", "0")).lower() in (
                "1",
                "true",
                "yes",
            ):
                return True
            prompts_cfg = (
                self.cfg.get("prompts", {})
                if isinstance(self.cfg.get("prompts", {}), dict)
                else {}
            )
            return bool(prompts_cfg.get("enabled", False))
        except Exception:
            return False

    def _prompt_template(self, name: str) -> Dict[str, Any] | None:
        templates: Dict[str, Dict[str, Any]] = {
            "handoff.next_steps": {
                "ok": True,
                "name": "handoff.next_steps",
                "description": "Summarize status and list next 3 concrete actions",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a concise senior engineer. Produce a brief handoff: status, risks, next 3 steps.",
                    },
                    {
                        "role": "user",
                        "content": "Context: {{summary}}\nPlan: {{plan_markdown}}",
                    },
                ],
            },
            "rules.summary": {
                "ok": True,
                "name": "rules.summary",
                "description": "Summarize compiled rules and enforcement gates",
                "messages": [
                    {
                        "role": "system",
                        "content": "Summarize coverage thresholds, gates, and security checks in bullet points.",
                    },
                    {
                        "role": "user",
                        "content": "Compiled Rules JSON: {{rules_compiled_json}}",
                    },
                ],
            },
        }
        return templates.get(name)

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
