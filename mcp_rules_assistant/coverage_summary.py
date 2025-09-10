from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from defusedxml import ElementTree as ET  # type: ignore

_log = logging.getLogger(__name__)


class ClassItem(TypedDict, total=False):
    file: str
    coverage: float
    lines_valid: int
    lines_covered: int
    threshold: float
    delta: float
    delta_up: float


def _cache_path(project_root: Path) -> Path:
    return (project_root / ".mcp/coverage_cache.json").resolve()


def _read_classes_with_cache(project_root: Path, coverage_xml: str) -> List[ClassItem]:
    path = (project_root / coverage_xml).resolve()
    items: List[ClassItem] = []
    if not path.exists():
        return items
    try:
        stat = path.stat()
        try:
            data_bytes = path.read_bytes()
        except (OSError, IOError):
            data_bytes = b""
        import hashlib

        sig_hash = hashlib.sha256(data_bytes).hexdigest()
        sig = f"{int(getattr(stat, 'st_mtime_ns', int(stat.st_mtime*1e9)))}-{stat.st_size}-{sig_hash}"
        cpath = _cache_path(project_root)
        cache: Dict[str, Any] = {}
        if cpath.exists():
            try:
                cache = json.loads(cpath.read_text(encoding="utf-8"))
            except Exception:
                cache = {}
        files = cache.get("files") or {}
        if isinstance(files, dict):
            cache_entry: Optional[Dict[str, Any]] = (
                files.get(str(path)) if isinstance(files.get(str(path)), dict) else None
            )
        else:
            cache_entry = None  # pragma: no cover (defensive branch)
        if (
            isinstance(cache_entry, dict)
            and cache_entry.get("sig") == sig
            and isinstance(cache_entry.get("items"), list)
        ):
            # cache hit
            return list(cache_entry.get("items") or [])  # type: ignore[return-value]
    except Exception as e:
        sig = ""
        cache = {}
        _log.debug("[coverage] cache probe failed: %r", e)
    # parse fresh
    try:
        tree = ET.parse(str(path))
        r = tree.getroot()
        for cls in r.findall(".//class"):
            filename = cls.get("filename") or ""
            line_rate = cls.get("line-rate")
            lines_valid = cls.get("lines-valid")
            lines_covered = cls.get("lines-covered")
            cov = None
            if line_rate is not None:
                try:
                    cov = float(line_rate)
                except ValueError:
                    cov = None
            if cov is None and lines_valid and lines_covered:
                try:
                    v = float(lines_valid)
                    c = float(lines_covered)
                    cov = (c / v) if v else 1.0
                except ValueError:
                    cov = None
            if cov is None:
                continue
            row: ClassItem = {"file": filename, "coverage": float(cov)}
            try:
                if lines_valid is not None and lines_covered is not None:
                    row["lines_valid"] = int(float(lines_valid))
                    row["lines_covered"] = int(float(lines_covered))
            except Exception:  # pragma: no cover (defensive parsing)
                pass
            items.append(row)
        # write cache
        try:
            cache.setdefault("files", {})
            if isinstance(cache["files"], dict):
                cache["files"][str(path)] = {"sig": sig, "items": items}
                cpath.parent.mkdir(parents=True, exist_ok=True)
                cpath.write_text(
                    json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
                )
        except Exception as e:  # pragma: no cover (I/O failures ignored)
            _log.debug("[coverage] cache write skipped: %r", e)
    except Exception as e:
        _log.debug("[coverage] parse failed, returning empty list: %r", e)
        return []
    return items


def _threshold_for_file(
    file: str, policy: Optional[Dict[str, float]], default: float
) -> float:
    """Decide threshold with priority: suffix match > prefix match > default.

    - Suffix means file.endswith(key) so a basename entry like "cli.py" wins.
    - Prefix means file.startswith(key) so a directory entry like "pkg/" applies.
    - For multiple matches of the same type, choose the longest key (most specific).
    """
    try:
        dflt = float(default)
    except Exception:
        dflt = 0.9
    if not policy or not isinstance(policy, dict):
        return dflt
    # Normalize and collect
    try:
        items: List[Tuple[str, float]] = [(str(k), float(v)) for k, v in policy.items()]
    except Exception:
        return dflt
    suffix = [(k, v) for k, v in items if file.endswith(k)]
    if suffix:
        k, v = max(suffix, key=lambda kv: len(kv[0]))
        return float(v)
    prefix = [(k, v) for k, v in items if file.startswith(k)]
    if prefix:
        k, v = max(prefix, key=lambda kv: len(kv[0]))
        return float(v)
    return dflt


def summarize(
    project_root: Optional[Path] = None,
    coverage_xml: str = "coverage.xml",
    policy: Optional[Dict[str, float]] = None,
    min_module: float = 0.9,
) -> Dict[str, object]:
    root = (project_root or Path.cwd()).resolve()
    path = root / coverage_xml
    if not path.exists():
        return {
            "ok": False,
            "message": f"{coverage_xml} not found. Run tests with --cov-report=xml.",
            "items": [],
        }
    items: List[ClassItem] = _read_classes_with_cache(root, coverage_xml)

    # 识别薄弱项
    weak: List[ClassItem] = []
    threshold = float(min_module)
    for it in items:
        name = str(it.get("file", ""))
        th: float = _threshold_for_file(name, policy, threshold)
        it["threshold"] = th
        cov_obj = it.get("coverage", 0.0)  # keep original for custom __lt__
        try:
            do_weak = bool(cov_obj < th)  # type: ignore[operator]
        except Exception:
            do_weak = False
        if do_weak:
            try:
                it["delta"] = float(th) - float(cov_obj)  # type: ignore[arg-type]
            except Exception:  # pragma: no cover (delta conversion may fail)
                pass
            weak.append(it)

    # sort by largest shortfall first
    def sort_key(x: ClassItem) -> float:
        try:
            return -float(x.get("delta", 0.0))
        except Exception:
            return 0.0

    weak_sorted = sorted(weak, key=sort_key)[:50]
    return {"ok": True, "count": len(items), "weak": weak_sorted}


def summarize_groups(
    project_root: Optional[Path] = None,
    coverage_xml: str = "coverage.xml",
    policy: Optional[Dict[str, float]] = None,
    min_module: float = 0.9,
) -> Dict[str, object]:
    root = (project_root or Path.cwd()).resolve()
    path = root / coverage_xml
    if not path.exists():
        return {
            "ok": False,
            "message": f"{coverage_xml} not found. Run tests with --cov-report=xml.",
            "groups": [],
        }
    items: List[ClassItem] = _read_classes_with_cache(root, coverage_xml)
    prefixes: List[Tuple[str, float]] = []
    if policy:
        # sort by longer prefix first for specificity
        prefixes = sorted(
            [(p, float(th)) for p, th in policy.items()],
            key=lambda x: len(x[0]),
            reverse=True,
        )
    groups: Dict[str, Dict[str, float]] = {}
    # init known groups
    for p, th in prefixes:
        groups[p] = {
            "covered": 0.0,
            "valid": 0.0,
            "weak": 0.0,
            "files": 0.0,
            "threshold": th,
        }
    groups["other"] = {
        "covered": 0.0,
        "valid": 0.0,
        "weak": 0.0,
        "files": 0.0,
        "threshold": float(min_module),
    }

    def pick_prefix(file: str) -> str:
        # 优先使用“后缀匹配”（basename），再回退到“前缀匹配”（目录）。
        # 同一匹配类型下选择更具体（更长）的键。
        # 构造时 prefixes 已按长度降序，因此可直接按顺序扫描。
        # 1) 后缀优先（如 cli.py 应优先于 mcp_rules_assistant/）。
        for p, _th in prefixes:
            if file.endswith(p):
                return p
        # 2) 再考虑前缀（目录级策略）。
        for p, _th in prefixes:
            if file.startswith(p):
                return p
        return "other"

    for cls in items:
        filename = str(cls.get("file") or "")
        cov: Optional[float] = None
        try:
            cov = float(cls.get("coverage", 0.0))
        except Exception:
            cov = None
        v = 0.0
        c = 0.0
        try:
            v = float(cls.get("lines_valid", 0.0))
            c = float(cls.get("lines_covered", (cov or 0.0) * v))
        except Exception:
            v = 0.0
            c = 0.0
        # Fallback: when class entry lacks lines_valid/lines_covered, approximate by weighting 1 file
        if v <= 0.0 and cov is not None:
            v = 1.0
            c = cov * v
        if cov is None:
            continue
        gname = pick_prefix(filename)
        g = groups[gname]
        g["files"] += 1.0
        g["valid"] += v
        g["covered"] += c
        th = g.get("threshold", float(min_module))
        if cov < th:
            g["weak"] += 1.0

    out_groups: List[Dict[str, object]] = []
    for name, g in groups.items():
        cov = (g["covered"] / g["valid"]) if g["valid"] > 0 else 1.0
        out_groups.append(
            {
                "prefix": name,
                "coverage": cov,
                "threshold": g.get("threshold", float(min_module)),
                "weak_count": int(g["weak"]),
                "files_count": int(g["files"]),
            }
        )

    def _key_cov(d: Dict[str, object]) -> float:
        v = d.get("coverage", 0.0)
        if isinstance(v, (int, float, str)):
            try:
                return float(v)
            except Exception:  # pragma: no cover
                return 0.0
        return 0.0

    out_groups_sorted = sorted(out_groups, key=_key_cov)
    return {"ok": True, "groups": out_groups_sorted}


def summarize_near(
    project_root: Optional[Path] = None,
    coverage_xml: str = "coverage.xml",
    policy: Optional[Dict[str, float]] = None,
    min_module: float = 0.9,
    within: float = 0.03,
    top: int = 50,
) -> Dict[str, object]:
    """列出“未低于阈值但距离阈值不超过 within”的文件。

    within: 小数（0.03 表示 3%）。
    """
    root = (project_root or Path.cwd()).resolve()
    path = root / coverage_xml
    if not path.exists():
        return {
            "ok": False,
            "message": f"{coverage_xml} not found. Run tests with --cov-report=xml.",
            "items": [],
        }
    items: List[ClassItem] = _read_classes_with_cache(root, coverage_xml)

    def threshold_for(file: str) -> float:
        return _threshold_for_file(file, policy, float(min_module))

    near: List[Dict[str, object]] = []
    for it in items:
        th = threshold_for(str(it.get("file", "")))
        cov = float(it.get("coverage", 0.0))
        if cov >= th:
            gap = cov - th
            if gap <= float(within) + 1e-12:
                out: Dict[str, object] = dict(it)
                out["threshold"] = th
                out["delta_up"] = gap
                near.append(out)

    def _key_delta(d: Dict[str, object]) -> float:
        v = d.get("delta_up", 0.0)
        if isinstance(v, (int, float, str)):
            try:
                return float(v)
            except Exception:  # pragma: no cover
                return 0.0
        return 0.0

    near_sorted = sorted(near, key=_key_delta)[: int(top)]
    return {"ok": True, "near": near_sorted}


def summarize_tree(
    project_root: Optional[Path] = None,
    coverage_xml: str = "coverage.xml",
    policy: Optional[Dict[str, float]] = None,
    min_module: float = 0.9,
    max_depth: int = 3,
) -> Dict[str, object]:
    """构建薄弱文件的目录树（浅层），用于 UI 展示。

    输出结构：{"ok": bool, "tree": {"name": "/", "children": { name: node }, "files": [weak...] }}
    """
    base = summarize(
        project_root=project_root,
        coverage_xml=coverage_xml,
        policy=policy,
        min_module=min_module,
    )
    if not base.get("ok"):
        return base
    weak_raw = base.get("weak", [])
    weak: List[Dict[str, object]] = weak_raw if isinstance(weak_raw, list) else []
    root: Dict[str, object] = {"name": "/", "children": {}, "files": []}

    def get_child(node: Dict[str, object], name: str) -> Dict[str, object]:
        children = node.setdefault(
            "children", {}
        )  # may be corrupted by external writes
        if not isinstance(children, dict):  # defensive: avoid assert in optimized mode
            children = {}
            node["children"] = children
        if name not in children:
            children[name] = {"name": name, "children": {}, "files": []}
        return children[name]  # type: ignore[return-value]

    for w in weak:  # type: ignore[assignment]
        file = str(w.get("file", ""))
        parts = [p for p in file.split("/") if p]
        node = root
        for i, p in enumerate(parts[:max_depth]):
            node = get_child(node, p)
        # 挂到当前 node 的 files
        files = node.setdefault("files", [])
        if not isinstance(files, list):  # defensive: normalize type
            files = []
            node["files"] = files
        files.append(w)
    return {"ok": True, "tree": root}
