from __future__ import annotations

import json
import os
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
from .fs_wrapper import FSGuard
from .memory import MemoryManager
from .rules import Complexity, DevMode, Scenario, choose_thresholds, explain_thresholds
from .tools import registry, setup_default_tools


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
                caps: Dict[str, Any] = {"tools": True, "resources": True, "prompts": True}
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
                    snap = self.mm.snapshot()
                    result = {
                        "mimeType": "application/json",
                        "text": json.dumps(snap, ensure_ascii=False),
                    }
                elif uri.startswith("rules://"):
                    if uri.endswith("/compiled"):
                        path = self.project_root / ri.COMPILED_MD
                        mime = "text/markdown"
                    elif uri.endswith("/compiled.json"):
                        path = self.project_root / ri.COMPILED_JSON
                        mime = "application/json"
                    elif uri.endswith("/suggestions"):
                        path = self.project_root / ri.SUGGESTIONS_MD
                        mime = "text/markdown"
                    elif uri.endswith("/maxima"):
                        # read maxima from compiled.json meta
                        pjson = self.project_root / ri.COMPILED_JSON
                        if not pjson.exists():
                            raise ValueError(
                                "rules resource not found; run rules.ingest first"
                            )
                        import json as _json

                        try:
                            data = _json.loads(pjson.read_text(encoding="utf-8"))
                        except Exception:
                            data = {}
                        maxima = {}
                        meta = data.get("meta", {}) or {}
                        if isinstance(meta.get("maxima", {}), dict):
                            maxima = meta.get("maxima", {})
                        result = {
                            "mimeType": "application/json",
                            "text": _json.dumps({"maxima": maxima}, ensure_ascii=False),
                        }
                        return {"jsonrpc": "2.0", "id": req_id, "result": result}
                    else:
                        raise ValueError("unknown rules resource")
                    if not path.exists():
                        raise ValueError(
                            "rules resource not found; run rules.ingest first"
                        )
                    result = {
                        "mimeType": mime,
                        "text": path.read_text(encoding="utf-8"),
                    }
                elif uri.startswith("coverage://"):
                    # 动态读取当前项目配置，避免初始化时的 cwd 影响（测试/多项目场景）
                    cfg_now = load_config(self.project_root)
                    perf = (
                        cfg_now.get("performance", {})
                        if isinstance(cfg_now.get("performance", {}), dict)
                        else {}
                    )
                    min_module = float(
                        (perf.get("on_push", {}) or {})
                        .get("coverage", {})
                        .get("min_module", 0.9)
                    )
                    # 未来可扩展 per-module policy；当前读取 config 中的 coverage.policy 可选字段
                    policy = (
                        (cfg_now.get("coverage", {}) or {}).get("policy", None)
                        if isinstance(cfg_now.get("coverage", {}), dict)
                        else None
                    )
                    if uri.endswith("/groups"):
                        summary = covsum.summarize_groups(
                            project_root=self.project_root,
                            policy=policy,
                            min_module=min_module,
                        )
                        result = {
                            "mimeType": "application/json",
                            "text": json.dumps(summary, ensure_ascii=False),
                        }
                    elif uri.endswith("/tree"):
                        summary = covsum.summarize_tree(
                            project_root=self.project_root,
                            policy=policy,
                            min_module=min_module,
                        )
                        result = {
                            "mimeType": "application/json",
                            "text": json.dumps(summary, ensure_ascii=False),
                        }
                    elif uri.endswith("/near"):
                        # 默认窗口与 Top 可由配置覆盖（coverage.near）
                        near_cfg = (
                            (self.cfg.get("coverage", {}) or {}).get("near", {})
                            if isinstance(self.cfg.get("coverage", {}), dict)
                            else {}
                        )
                        within = float((near_cfg or {}).get("within", 0.03))
                        top = int((near_cfg or {}).get("top", 50))
                        summary = covsum.summarize_near(
                            project_root=self.project_root,
                            policy=policy,
                            min_module=min_module,
                            within=within,
                            top=top,
                        )
                        result = {
                            "mimeType": "application/json",
                            "text": json.dumps(summary, ensure_ascii=False),
                        }
                    elif uri.endswith("/report"):
                        near_cfg = (
                            (self.cfg.get("coverage", {}) or {}).get("near", {})
                            if isinstance(self.cfg.get("coverage", {}), dict)
                            else {}
                        )
                        within = float((near_cfg or {}).get("within", 0.03))
                        top = int((near_cfg or {}).get("top", 50))
                        res_sum = covsum.summarize(
                            project_root=self.project_root,
                            policy=policy,
                            min_module=min_module,
                        )
                        res_grp = covsum.summarize_groups(
                            project_root=self.project_root,
                            policy=policy,
                            min_module=min_module,
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
                        result = {
                            "mimeType": "application/json",
                            "text": json.dumps(payload, ensure_ascii=False),
                        }
                    else:
                        summary = covsum.summarize(
                            project_root=self.project_root,
                            policy=policy,
                            min_module=min_module,
                        )
                        result = {
                            "mimeType": "application/json",
                            "text": json.dumps(summary, ensure_ascii=False),
                        }
                elif uri.startswith("progress://"):
                    text = progress_mod.read_plan(self.project_root)
                    result = {"mimeType": "text/markdown", "text": text}
                elif uri.startswith("config://"):
                    cfg_file = self.project_root / DEFAULT_PROJECT_CONFIG_PATH
                    text = (
                        cfg_file.read_text(encoding="utf-8")
                        if cfg_file.exists()
                        else ""
                    )
                    result = {"mimeType": "text/yaml", "text": text}
                elif uri.startswith("ci://"):
                    ci_file = self.project_root / ".github/workflows/ci.yml"
                    text = (
                        ci_file.read_text(encoding="utf-8") if ci_file.exists() else ""
                    )
                    result = {"mimeType": "text/yaml", "text": text}
                else:
                    raise ValueError("Unknown resource uri")
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
            return {"ok": True}
        if name == "memory.toggle_auto":
            on = bool(args.get("on", True))
            self.settings["memory_auto"] = on
            return {"ok": True, "auto": on}
        if name == "memory.snapshot":
            return self.mm.snapshot()
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
            paths = args.get("paths", [])
            if not paths:
                raise ValueError("paths required")
            res = ri.ingest(paths, project_root=self.project_root)
            return res
        if name == "rules.validate":
            res = ri.compile_rules(project_root=self.project_root)
            return res
        if name == "env.prepare":
            # 轻量实现：支持 dry-run 规划，或实际创建 venv 并可选安装基础工具
            import subprocess

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
                    subprocess.run(
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
                    # 升级 pip 与安装工具链（尽量不中断）
                    subprocess.run(
                        [str(py_bin), "-m", "pip", "install", "--upgrade", "pip"],
                        cwd=self.project_root,
                        check=False,
                    )
                    if packages:
                        subprocess.run(
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
        if name == "env.diagnose":
            import platform
            import shutil

            cfg_now = load_config(self.project_root)
            perf = (
                cfg_now.get("performance", {})
                if isinstance(cfg_now.get("performance", {}), dict)
                else {}
            )
            min_module = float(
                (perf.get("on_push", {}) or {})
                .get("coverage", {})
                .get("min_module", 0.9)
            )
            coverage_exists = (self.project_root / "coverage.xml").exists()
            compiled_json = self.project_root / ri.COMPILED_JSON
            compiled_exists = compiled_json.exists()
            maxima = {}
            if compiled_exists:
                try:
                    import json as _json

                    data = _json.loads(compiled_json.read_text(encoding="utf-8"))
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
            return {
                "ok": True,
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "tools": tools,
                "config": {"min_module": min_module},
                "coverage": {"exists": coverage_exists},
                "rules": {"compiled_exists": compiled_exists},
                "maxima": maxima,
            }
        if name == "coverage.near":
            cfg_now = load_config(self.project_root)
            # defaults from config (coverage.near), can be overridden by args
            near_cfg = (
                (cfg_now.get("coverage", {}) or {}).get("near", {})
                if isinstance(cfg_now.get("coverage", {}), dict)
                else {}
            )
            within = float(args.get("within", near_cfg.get("within", 0.03)))
            top = int(args.get("top", near_cfg.get("top", 50)))
            perf = (
                cfg_now.get("performance", {})
                if isinstance(cfg_now.get("performance", {}), dict)
                else {}
            )
            min_module = float(
                (perf.get("on_push", {}) or {})
                .get("coverage", {})
                .get("min_module", 0.9)
            )
            policy = (
                (cfg_now.get("coverage", {}) or {}).get("policy", None)
                if isinstance(cfg_now.get("coverage", {}), dict)
                else None
            )
            data = covsum.summarize_near(
                project_root=self.project_root,
                policy=policy,
                min_module=min_module,
                within=within,
                top=top,
            )
            return data
        if name == "coverage.report":
            cfg_now = load_config(self.project_root)
            perf = (
                cfg_now.get("performance", {})
                if isinstance(cfg_now.get("performance", {}), dict)
                else {}
            )
            min_module = float(
                (perf.get("on_push", {}) or {})
                .get("coverage", {})
                .get("min_module", 0.9)
            )
            policy = (
                (cfg_now.get("coverage", {}) or {}).get("policy", None)
                if isinstance(cfg_now.get("coverage", {}), dict)
                else None
            )
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
        if name == "rules.maxima":
            pjson = self.project_root / ri.COMPILED_JSON
            if not pjson.exists():
                return {"ok": False, "message": "compiled rules not found"}
            import json as _json

            try:
                data = _json.loads(pjson.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            meta = data.get("meta", {}) or {}
            maxima = (
                meta.get("maxima", {})
                if isinstance(meta.get("maxima", {}), dict)
                else {}
            )
            return {"ok": True, "maxima": maxima}
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
                p = Path(f["path"])
                if not dry_run:
                    self.fs.write_text(p, content)
                changed_paths.append((self.project_root / p).resolve())
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
            paths = hooks_mod.install_git_hooks(self.project_root)
            return {"ok": True, "installed": paths}
        if name == "nl.command":
            text = args.get("text", "")
            mapped = nl_mod.parse(text)
            return {"ok": True, "parsed": {"tool": mapped, "text": text}}
        if name == "plan.update":
            text = args.get("text", "")
            if not text:
                raise ValueError("text required")
            progress_mod.write_plan(text, self.project_root)
            return {"ok": True}
        if name == "plan.set":
            status = args.get("status")
            current = args.get("current")
            nxt = args.get("next")
            progress_mod.update_plan_fields(
                self.project_root, status=status, current=current, nxt=nxt
            )
            return {"ok": True}
        if name == "config.get":
            cfg_path = self.project_root / DEFAULT_PROJECT_CONFIG_PATH
            ensure_project_config(cfg_path)
            try:
                raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            except Exception:
                raw = {}
            section = args.get("section")
            return {"ok": True, "config": raw.get(section, raw) if section else raw}
        if name == "config.update":
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
            cfg_path.write_text(
                yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            self.cfg = load_config(self.project_root)
            return {"ok": True, "ci": ci}
        if name == "ci.generate":
            ci_path = hooks_mod.generate_github_ci(self.project_root)
            return {"ok": True, "path": str(ci_path)}
        if name == "ci.validate":
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
        if name == "ci.autofix":
            res = hooks_mod.autofix_github_ci(self.project_root)
            return {"ok": True, **res}
        if name == "rules.enforce":
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
                perf.get("on_push", {})
                if isinstance(perf.get("on_push", {}), dict)
                else {}
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
                policy.get("container.required")
                or policy.get("container.policy.baseline")
            ) and not bool(ci.get("hadolint", False)):
                ci["hadolint"] = True
                ci_changed = True
            if bool(policy.get("security.sast_strict")) and not ci.get(
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
            if bool(policy.get("security.secrets_scan")) or bool(
                policy.get("container.policy.baseline")
            ):
                needs_hooks = True
            # 写回配置
            if changed:
                cfg_path.write_text(
                    yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
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
                ("security.secrets_scan", "secrets_scan"),
                ("security.sast_strict", "sast_strict"),
                ("container.required", "container_required"),
                ("container.policy.baseline", "container_baseline"),
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
        raise ValueError(f"Unknown tool: {name}")

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
