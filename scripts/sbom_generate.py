#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _read_pyproject(root: Path) -> Dict[str, Any]:
    import sys

    p = root / "pyproject.toml"
    if not p.exists():
        return {}
    try:
        if sys.version_info >= (3, 11):
            import tomllib  # type: ignore

            data = tomllib.loads(p.read_text(encoding="utf-8"))
        else:  # pragma: no cover
            import toml  # type: ignore

            data = toml.loads(p.read_text(encoding="utf-8"))
        return data or {}
    except Exception:
        return {}


def _python_deps(root: Path) -> List[Dict[str, str]]:
    data = _read_pyproject(root)
    deps = []
    try:
        for spec in (data.get("project", {}) or {}).get("dependencies", []) or []:
            if isinstance(spec, str):
                # Split name + version (best-effort)
                name = spec
                ver = ""
                for sep in ["==", ">=", "<=", "~=", "!=", ">", "<"]:
                    if sep in spec:
                        name, ver = spec.split(sep, 1)
                        name = name.strip()
                        ver = f"{sep}{ver.strip()}"
                        break
                deps.append({"name": name, "spec": ver})
    except Exception:
        pass
    return deps


def _node_deps(root: Path) -> List[Dict[str, str]]:
    lock = root / "extensions" / "vscode" / "package-lock.json"
    if not lock.exists():
        return []
    try:
        data = json.loads(lock.read_text(encoding="utf-8"))
        pkgs = data.get("packages") or {}
        out: List[Dict[str, str]] = []
        if isinstance(pkgs, dict):
            for k, v in pkgs.items():
                if not isinstance(v, dict):
                    continue
                name = v.get("name") or (k.split("node_modules/")[-1] if "node_modules/" in k else None)
                version = v.get("version")
                if name and version:
                    out.append({"name": str(name), "version": str(version)})
        return out
    except Exception:
        return []


def main() -> None:
    root = Path.cwd().resolve()
    out_dir = root / ".mcp" / "dashboard"
    out_dir.mkdir(parents=True, exist_ok=True)
    sbom = {
        "project": str(root),
        "python": _python_deps(root),
        "node": _node_deps(root),
    }
    (out_dir / "sbom.json").write_text(json.dumps(sbom, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(out_dir / 'sbom.json'), "py": len(sbom["python"]), "node": len(sbom["node"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()

