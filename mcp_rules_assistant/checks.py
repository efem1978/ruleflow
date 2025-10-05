from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import cast

import yaml  # type: ignore[import-untyped]

# 可选委托到统一的 process.run_cmd（默认关闭，保持向后兼容测试桩行为）。
# 开启方式：
#  - 环境变量 MCP_CHECKS_PROCESS_RUNNER=1
#  - 或项目配置 `.mcp/assistant.yaml` 中设置 execution.checks_delegate_run_cmd: true
try:  # 仅在需要时导入，避免冷启动额外依赖
    from .config import load_config as _load_cfg  # type: ignore
    from .process import run_cmd as _proc_run_cmd  # type: ignore
except Exception:  # pragma: no cover - 在极端环境下回退
    _load_cfg = None  # type: ignore
    _proc_run_cmd = None  # type: ignore

_USE_PROC_RUNNER_CACHE: bool | None = None


def _use_process_runner(project_root: Path | None) -> bool:
    global _USE_PROC_RUNNER_CACHE
    env = os.environ.get("MCP_CHECKS_PROCESS_RUNNER")
    if env in ("1", "true", "True"):
        return True
    if env in ("0", "false", "False"):
        return False
    if _USE_PROC_RUNNER_CACHE is not None:
        return _USE_PROC_RUNNER_CACHE
    # 配置优先（execution.checks_delegate_run_cmd: true）
    use = False
    try:
        if _load_cfg is not None:
            root = (project_root or Path.cwd()).resolve()
            cfg = _load_cfg(root)
            ex = (
                cfg.get("execution", {})
                if isinstance(cfg.get("execution", {}), dict)
                else {}
            )
            use = bool(ex.get("checks_delegate_run_cmd", False))
    except Exception:
        use = False
    _USE_PROC_RUNNER_CACHE = use
    return use


def _run(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, object]:
    """运行外部命令：默认直接使用 subprocess.run；当开启委托开关时，使用统一的 process.run_cmd。

    返回结构保持：{ok, code, stdout, stderr, cmd}；若可执行缺失返回 skipped。
    """
    # 优先尝试 process.run_cmd（可配置）
    if _use_process_runner(cwd) and _proc_run_cmd is not None:
        try:
            p = _proc_run_cmd(
                cmd,
                cwd=(cwd or Path.cwd()),
                capture_stdout=True,
                env=env,
                check=False,
            )
            return {
                "ok": getattr(p, "returncode", 0) == 0,
                "code": getattr(p, "returncode", 0),
                "stdout": getattr(p, "stdout", ""),
                "stderr": getattr(p, "stderr", ""),
                "cmd": cmd,
            }
        except FileNotFoundError:
            return {
                "ok": True,
                "skipped": True,
                "reason": f"{cmd[0]} not found",
                "cmd": cmd,
            }
        except Exception as e:
            # 回退到本地实现，保证兼容性
            import logging

            logging.getLogger(__name__).debug(
                "[checks] delegate run_cmd fallback: %r",
                e,
            )
    # 兼容旧实现：直接 subprocess.run，并从原生 subprocess 模块获取 PIPE
    try:
        try:
            import importlib

            _std_sub = importlib.import_module("subprocess")
            _pipe = getattr(_std_sub, "PIPE", None)
        except Exception:
            _pipe = None
        kwargs = {"cwd": cwd, "text": True, "env": env}
        if _pipe is not None:
            kwargs.update({"stdout": _pipe, "stderr": _pipe})
        p = subprocess.run(cmd, **kwargs)  # type: ignore[arg-type]
        return {
            "ok": p.returncode == 0,
            "code": p.returncode,
            "stdout": getattr(p, "stdout", ""),
            "stderr": getattr(p, "stderr", ""),
            "cmd": cmd,
        }
    except FileNotFoundError:
        return {
            "ok": True,
            "skipped": True,
            "reason": f"{cmd[0]} not found",
            "cmd": cmd,
        }


def run_lint(files: list[Path], cwd: Path | None = None) -> dict[str, object]:
    # 改动文件使用 ruff 检查，若不存在则跳过
    targets = [str(f) for f in files if f.suffix in {".py"}]
    if not targets:
        return {"ok": True, "skipped": True, "reason": "no python files"}
    # 兼容新版 Ruff 子命令：使用 `ruff check`，避免旧式顶层参数不兼容
    return _run(["ruff", "check", "--quiet", *targets], cwd)


def run_typecheck(cwd: Path | None = None) -> dict[str, object]:
    # 优先 mypy；不存在则跳过
    return _run(["mypy", "."], cwd)


LAST_FAIL_FILE = Path(".mcp/last_failed_tests.json")
TEST_INDEX_FILE = Path(".mcp/test_index.json")
TEST_INDEX_META = Path(".mcp/test_index_meta.json")


def _read_last_fail(project_root: Path) -> dict[str, set[str] | dict[str, int]]:
    path = project_root / LAST_FAIL_FILE
    if not path.exists():
        return {"tests": set(), "nodeids": set(), "test_counts": {}, "node_counts": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            "tests": set(data.get("tests", [])),
            "nodeids": set(data.get("nodeids", [])),
            "test_counts": dict(data.get("test_counts", {})),
            "node_counts": dict(data.get("node_counts", {})),
        }
    except Exception:
        return {"tests": set(), "nodeids": set(), "test_counts": {}, "node_counts": {}}


def _write_last_fail(
    project_root: Path,
    tests: set[str],
    nodeids: set[str],
    test_counts: dict[str, int],
    node_counts: dict[str, int],
    events: list[dict[str, str]] | None = None,
) -> None:
    path = project_root / LAST_FAIL_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "tests": sorted(tests),
                "nodeids": sorted(nodeids),
                "test_counts": test_counts,
                "node_counts": node_counts,
                "events": events or [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _module_import_candidates(project_root: Path, file: Path) -> list[str]:
    # 简单从路径推导模块导入名：a/b/c.py -> a.b.c
    rel = file.resolve().relative_to(project_root.resolve())
    parts = list(rel.parts)
    if parts and parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return [".".join(parts)] if parts else []


def _discover_tests_by_import(project_root: Path, candidates: list[str]) -> set[str]:
    tests_dir = project_root / "tests"
    result: set[str] = set()
    if not tests_dir.exists():
        return result
    for p in tests_dir.rglob("test_*.py"):
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue  # nosec B112 - skip unreadable test file
        low = txt.lower()
        for mod in candidates:
            if f"import {mod.lower()}" in low or f"from {mod.lower()}" in low:
                result.add(str(p))
                break
    return result


def _compute_tests_signature(project_root: Path) -> str:
    tests_dir = project_root / "tests"
    # Use SHA-256 for non-security test-set signature to satisfy bandit
    h = hashlib.sha256()
    if tests_dir.exists():
        for p in sorted(tests_dir.rglob("test_*.py")):
            try:
                st = p.stat()
                h.update(str(p.relative_to(project_root)).encode("utf-8"))
                h.update(str(int(st.st_mtime)).encode("utf-8"))
                h.update(str(st.st_size).encode("utf-8"))
            except Exception:
                continue  # nosec B112 - skip files with stat/read errors
    return h.hexdigest()


def _write_index_meta(project_root: Path, sig: str) -> None:
    meta_path = project_root / TEST_INDEX_META
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        meta_path.write_text(
            json.dumps({"sig": sig}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass  # nosec B110 - cache write errors are non-fatal


def _read_index_meta(project_root: Path) -> str:
    meta_path = project_root / TEST_INDEX_META
    if not meta_path.exists():
        return ""
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return str(data.get("sig") or "")
    except Exception:
        return ""


def build_test_index(project_root: Path) -> dict[str, list[str]]:
    tests_dir = project_root / "tests"
    index: dict[str, list[str]] = {}
    if not tests_dir.exists():
        # 也写入空签名，避免下次重复尝试
        _write_index_meta(project_root, _compute_tests_signature(project_root))
        return index
    for p in tests_dir.rglob("test_*.py"):
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue  # nosec B112 - skip unreadable import candidates
        low = txt.lower()
        # 简单抽取 from x.y import ... 或 import x.y
        for line in low.splitlines():
            line = line.strip()
            if line.startswith("from "):
                mod = line.split()[1]
                index.setdefault(mod, []).append(str(p))
            elif line.startswith("import "):
                # import a, b.c -> 仅取第一个模块
                mods = line.split()[1].split(",")
                if mods:
                    index.setdefault(mods[0].strip(), []).append(str(p))
    # 去重
    for k, v in list(index.items()):
        index[k] = sorted(set(v))
    # 写入缓存
    (project_root / TEST_INDEX_FILE).parent.mkdir(parents=True, exist_ok=True)
    (project_root / TEST_INDEX_FILE).write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_index_meta(project_root, _compute_tests_signature(project_root))
    return index


def load_test_index(project_root: Path) -> dict[str, list[str]]:
    path = project_root / TEST_INDEX_FILE
    # 若不存在索引，返回空
    if not path.exists():
        return {}
    # 读取已存在索引
    idx: dict[str, list[str]] = {}
    try:
        idx = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        idx = {}
    # 检测签名，若变更则重建
    current_sig = _compute_tests_signature(project_root)
    saved_sig = _read_index_meta(project_root)
    if current_sig and current_sig != saved_sig:
        return build_test_index(project_root)
    return idx


def run_quick_tests(files: list[Path], cwd: Path | None = None) -> dict[str, object]:
    """运行受影响测试（启发式）：
    - 若改动包含测试文件，直接运行这些测试
    - 否则尝试根据源文件推导测试文件：tests/test_<name>.py 或 <name>_test.py
    """
    test_paths: set[str] = set()
    project_root = (cwd or Path.cwd()).resolve()
    # 尝试加载或构建测试索引
    index = load_test_index(project_root)
    if not index:
        index = build_test_index(project_root)

    for f in files:
        name = f.name
        # 1) 改动就是测试（仅限 Python 测试文件）
        if f.suffix == ".py" and (
            name.startswith("test_")
            or name.endswith("_test.py")
            or f.parent.name == "tests"
        ):
            test_paths.add(str(f))
            continue
        # 2) 推导匹配的测试
        if f.suffix == ".py":
            stem = f.stem
            candidates = [
                f"tests/test_{stem}.py",
                f"tests/{stem}_test.py",
            ]
            for c in candidates:
                p = project_root / c
                if p.exists():
                    test_paths.add(str(p))
            # 导入关系匹配
            imps = _module_import_candidates(
                project_root,
                (project_root / f).resolve() if not f.is_absolute() else f,
            )
            # 1) 使用索引命中
            for mod in imps:
                if mod in index:
                    test_paths.update(index[mod])
            # 2) 索引未命中时回退扫描
            if not test_paths:
                test_paths.update(_discover_tests_by_import(project_root, imps))
    # 合并上次失败缓存
    last_fail = _read_last_fail(project_root)
    test_paths.update(last_fail["tests"])  # type: ignore[index]
    nodeids = set(cast(set[str], last_fail.get("nodeids", set())))
    test_counts = cast(dict[str, int], last_fail.get("test_counts", {}))
    node_counts = cast(dict[str, int], last_fail.get("node_counts", {}))
    if not test_paths:
        return {"ok": True, "skipped": True, "reason": "no impacted tests"}

    # 优先级排序：按历史失败次数降序，未知为0
    # 基于失败次数与近期失败的加权排序（近3天+2，近7天+1）
    def sort_by_count(
        items: list[str],
        counts: dict[str, int],
        recent_bonus: dict[str, int],
    ) -> list[str]:
        return sorted(
            items,
            key=lambda x: (recent_bonus.get(x, 0), counts.get(x, 0)),
            reverse=True,
        )

    # 读取配置：失败加权策略
    decay_cfg = {
        "high_days": 3,
        "high_bonus": 2,
        "mid_days": 7,
        "mid_bonus": 1,
        "history_limit": 400,
    }
    try:
        cfg_path = project_root / ".mcp/assistant.yaml"
        if cfg_path.exists():
            y = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            d = (y.get("tests", {}) or {}).get("quick_fail_decay", {}) or {}
            for k in decay_cfg.keys():
                if k in d and d[k] is not None:
                    decay_cfg[k] = d[k]
    except Exception:
        pass  # nosec B110 - config read/parsing failure ignored for quick tests

    # 读取事件并构造近期加权
    events: list[dict[str, str]] = []
    try:
        raw = json.loads((project_root / LAST_FAIL_FILE).read_text(encoding="utf-8"))
        events = raw.get("events", []) or []
    except Exception:
        events = []
    now = time.time()
    bonus_tests: dict[str, int] = {}
    bonus_nodes: dict[str, int] = {}
    for ev in events:
        ts = float(ev.get("ts", 0))
        nid = ev.get("nodeid") or ""
        file_str = ev.get("file") or ""
        if not ts:
            continue
        age = now - ts
        if age <= float(decay_cfg["high_days"]) * 24 * 3600:
            if file_str:
                bonus_tests[file_str] = max(
                    bonus_tests.get(file_str, 0),
                    int(decay_cfg["high_bonus"]),
                )
            if nid:
                bonus_nodes[nid] = max(
                    bonus_nodes.get(nid, 0),
                    int(decay_cfg["high_bonus"]),
                )
        elif age <= float(decay_cfg["mid_days"]) * 24 * 3600:
            if file_str:
                bonus_tests[file_str] = max(
                    bonus_tests.get(file_str, 0),
                    int(decay_cfg["mid_bonus"]),
                )
            if nid:
                bonus_nodes[nid] = max(
                    bonus_nodes.get(nid, 0),
                    int(decay_cfg["mid_bonus"]),
                )

    ordered_tests = sort_by_count(sorted(test_paths), test_counts, bonus_tests)
    ordered_nodes = sort_by_count(sorted(nodeids), node_counts, bonus_nodes)

    # 如果有具体的 nodeid，则从 test_paths 中移除对应的文件，避免重复运行
    if ordered_nodes:
        node_files = {node.split("::")[0] for node in ordered_nodes}
        ordered_tests = [
            t
            for t in ordered_tests
            if t not in node_files and Path(t).name not in node_files
        ]

    py = sys.executable or "python3"
    cmd = [
        py,
        "-m",
        "pytest",
        "-q",
        "-p",
        "pytest_cov",
        "-p",
        "pytest_benchmark",
        "--maxfail=1",
        "--disable-warnings",
        "-W",
        "error",
        "--strict-markers",
        *ordered_tests,
        *ordered_nodes,
    ]
    # 保证被测工程根目录在 PYTHONPATH 中，避免通过 tests/ 路径运行时 import 失败
    env: dict[str, str] = os.environ.copy()
    root: str = str(project_root)
    env["PYTHONPATH"] = root + (
        ":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    res = _run(cmd, cwd, env=env)
    # 解析失败用例写回缓存（启发式）
    failed_files: set[str] = set()
    failed_nodes: set[str] = set()
    out = str(res.get("stdout") or "") + "\n" + str(res.get("stderr") or "")
    new_events: list[dict[str, str]] = events[
        -int(decay_cfg["history_limit"]) :
    ]  # 控制历史长度
    for line in out.splitlines():
        line = line.strip()
        # 形如: FAILED tests/test_x.py::TestClass::test_y - AssertionError
        if line.startswith("FAILED ") and ".py" in line:
            node = line.split()[1]
            file_part = node.split("::")[0]
            fpath = str((project_root / file_part).resolve())
            failed_files.add(fpath)
            failed_nodes.add(node)
            # 统计计数
            test_counts[fpath] = test_counts.get(fpath, 0) + 1
            node_counts[node] = node_counts.get(node, 0) + 1
            new_events.append({"nodeid": node, "file": fpath, "ts": str(now)})
    _write_last_fail(
        project_root,
        failed_files,
        failed_nodes,
        test_counts,
        node_counts,
        new_events,
    )
    return res


def run_checks(
    files: list[Path],
    cwd: Path | None = None,
    do_lint: bool = True,
    do_type: bool = False,
    do_quick_tests: bool = True,
) -> dict[str, object]:
    steps: list[dict[str, object]] = []
    results: dict[str, object] = {"ok": True, "steps": steps}
    if do_lint:
        r = run_lint(files, cwd)
        steps.append({"lint": r})
        results["ok"] = results["ok"] and bool(r.get("ok", False))
    if do_type:
        r = run_typecheck(cwd)
        steps.append({"type": r})
        results["ok"] = results["ok"] and bool(r.get("ok", False))
    if do_quick_tests:
        r = run_quick_tests(files, cwd)
        steps.append({"tests": r})
        results["ok"] = results["ok"] and bool(r.get("ok", False))
    return results
