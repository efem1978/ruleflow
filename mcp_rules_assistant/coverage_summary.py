from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _cache_path(project_root: Path) -> Path:
    return (project_root / ".mcp/coverage_cache.json").resolve()


def _read_classes_with_cache(
    project_root: Path, coverage_xml: str
) -> List[Dict[str, object]]:
    path = (project_root / coverage_xml).resolve()
    items: List[Dict[str, object]] = []
    if not path.exists():
        return items
    try:
        stat = path.stat()
        try:
            data_bytes = path.read_bytes()
        except Exception:
            data_bytes = b""
        import hashlib

        sig_hash = hashlib.sha1(data_bytes).hexdigest()
        sig = f"{int(getattr(stat, 'st_mtime_ns', int(stat.st_mtime*1e9)))}-{stat.st_size}-{sig_hash}"
        cpath = _cache_path(project_root)
        cache: Dict[str, object] = {}
        if cpath.exists():
            try:
                cache = json.loads(cpath.read_text(encoding="utf-8"))
            except Exception:
                cache = {}
        files = cache.get("files") or {}
        if isinstance(files, dict):
            rec = (
                files.get(str(path)) if isinstance(files.get(str(path)), dict) else None
            )
        else:
            rec = None
        if (
            isinstance(rec, dict)
            and rec.get("sig") == sig
            and isinstance(rec.get("items"), list)
        ):
            # cache hit
            return list(rec.get("items") or [])  # type: ignore[return-value]
    except Exception:
        sig = ""
        cache = {}
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
            rec: Dict[str, object] = {"file": filename, "coverage": cov}
            try:
                if lines_valid is not None and lines_covered is not None:
                    rec["lines_valid"] = int(float(lines_valid))
                    rec["lines_covered"] = int(float(lines_covered))
            except Exception:
                pass
            items.append(rec)
        # write cache
        try:
            cache.setdefault("files", {})
            if isinstance(cache["files"], dict):
                cache["files"][str(path)] = {"sig": sig, "items": items}
                cpath.parent.mkdir(parents=True, exist_ok=True)
                cpath.write_text(
                    json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
                )
        except Exception:
            pass
    except Exception:
        return []
    return items


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
    items: List[Dict[str, object]] = _read_classes_with_cache(root, coverage_xml)

    # 识别薄弱项
    weak: List[Dict[str, object]] = []
    threshold = min_module
    if policy:
        # 简化：如匹配到前缀策略，则按策略阈值
        for it in items:
            for prefix, th in policy.items():
                if it["file"].startswith(prefix):
                    it["threshold"] = th
                    break
            it.setdefault("threshold", threshold)
            if it["coverage"] < it["threshold"]:
                try:
                    it["delta"] = float(it["threshold"]) - float(
                        it["coverage"]
                    )  # how much below threshold
                except Exception:
                    pass
                weak.append(it)
    else:
        for it in items:
            it["threshold"] = threshold
            if it["coverage"] < threshold:
                try:
                    it["delta"] = float(threshold) - float(
                        it["coverage"]
                    )  # how much below threshold
                except Exception:
                    pass
                weak.append(it)

    # sort by largest shortfall first
    def sort_key(x: Dict[str, object]) -> float:
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
    items: List[Dict[str, object]] = _read_classes_with_cache(root, coverage_xml)
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
        for p, _th in prefixes:
            if file.startswith(p):
                return p
        return "other"

    for cls in items:
        filename = str(cls.get("file") or "")
        cov = None
        try:
            cov = (
                float(cls.get("coverage")) if cls.get("coverage") is not None else None
            )
        except Exception:
            cov = None
        v = 0.0
        c = 0.0
        try:
            v = float(cls.get("lines_valid", 0.0))
            c = float(cls.get("lines_covered", cov * v if cov is not None else 0.0))
        except Exception:
            pass
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
    out_groups_sorted = sorted(out_groups, key=lambda x: (x["coverage"]))
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
    items: List[Dict[str, object]] = _read_classes_with_cache(root, coverage_xml)

    def threshold_for(file: str) -> float:
        if policy:
            for p, th in policy.items():
                if file.startswith(p):
                    return float(th)
        return float(min_module)

    near: List[Dict[str, object]] = []
    for it in items:
        th = threshold_for(str(it["file"]))
        cov = float(it["coverage"])  # type: ignore[arg-type]
        if cov >= th:
            gap = cov - th
            if gap <= float(within) + 1e-12:
                out = dict(it)
                out["threshold"] = th
                out["delta_up"] = gap
                near.append(out)

    near_sorted = sorted(near, key=lambda x: (x.get("delta_up", 0.0)))[: int(top)]
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
    weak = base.get("weak", [])  # type: ignore[assignment]
    root: Dict[str, object] = {"name": "/", "children": {}, "files": []}

    def get_child(node: Dict[str, object], name: str) -> Dict[str, object]:
        children = node.setdefault("children", {})  # type: ignore[assignment]
        assert isinstance(children, dict)
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
        files = node.setdefault("files", [])  # type: ignore[assignment]
        assert isinstance(files, list)
        files.append(w)
    return {"ok": True, "tree": root}
