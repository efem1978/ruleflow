from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .atomics import atomic_write_text as _atomic_write_text

DEFAULT_PROJECT_CONFIG_PATH = Path(".mcp/assistant.yaml")
DEFAULT_GLOBAL_CONFIG_PATH = Path.home() / ".mcp/assistant.yaml"


class PerformanceMode(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    STRICT = "strict"


@dataclass
class CoveragePolicy:
    enforce: bool = True
    min_module: float = 0.9  # 90% 最低级模块阈值
    min_core: float = 0.95  # 核心模块更高阈值，可选


@dataclass
class OnSave:
    format_on_save: bool = True
    lint_changed_only: bool = True
    typecheck_incremental: bool = False
    quick_tests: bool = False


@dataclass
class OnCommit:
    lint: bool = True
    typecheck_incremental: bool = True
    test_impacted: bool = True


@dataclass
class OnPush:
    test_all: bool = True
    coverage: CoveragePolicy = field(default_factory=CoveragePolicy)
    security_scan: bool = True
    mutation_test: bool = False  # 严格档或企业/机构开启


@dataclass
class PerformanceSettings:
    mode: PerformanceMode = PerformanceMode.FAST
    on_save: OnSave = field(default_factory=OnSave)
    on_commit: OnCommit = field(default_factory=OnCommit)
    on_push: OnPush = field(default_factory=OnPush)


@dataclass
class GlobalConfig:
    performance: PerformanceSettings = field(default_factory=PerformanceSettings)
    language: str = "python"
    bilingual: bool = True


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def _dump_yaml(path: Path, data: Dict[str, Any]) -> None:
    """Atomically write YAML to disk to avoid partial/corrupted files."""
    # Dump to string first, then atomic write
    yml = yaml.safe_dump(data, sort_keys=False, allow_unicode=True) or ""
    _atomic_write_text(path, yml)


def default_config_dict() -> Dict[str, Any]:
    return {
        "performance": {
            "mode": PerformanceMode.FAST.value,
            "on_save": {
                "format_on_save": True,
                "lint_changed_only": True,
                "typecheck_incremental": False,
                "quick_tests": False,
            },
            "on_commit": {
                "lint": True,
                "typecheck_incremental": True,
                "test_impacted": True,
            },
            "on_push": {
                "test_all": True,
                "coverage": {"enforce": True, "min_module": 0.9, "min_core": 0.95},
                "security_scan": True,
                "mutation_test": False,
            },
        },
        "language": "python",
        "bilingual": True,
        "coverage": {
            # 模块级阈值策略（可选）：键为文件前缀，值为阈值（0~1）
            # 例：{"src/core/": 0.95, "src/": 0.90}
            "policy": {},
            "near": {"within": 0.03, "top": 50},
        },
        "tests": {
            "quick_fail_decay": {
                # 失败历史加权策略（用于 quick tests 排序）
                "high_days": 3,
                "high_bonus": 2,
                "mid_days": 7,
                "mid_bonus": 1,
                "history_limit": 400,
            }
        },
        "execution": {
            # 写入后执行轻量增量检查（FSGuard），默认关闭；由 MCP fs.apply_patch 的 strict/检查控制
            "fs_guard_post_checks": False,
            # 严格模式：当 fs_guard_post_checks 启用且检查失败时，阻断写入
            "fs_guard_strict": False,
            # 允许受控写入的相对路径前缀白名单（留空表示不限制）。
            # 例：["mcp_rules_assistant/", "tests/", "docs/", ".mcp/"]
            "allowed_write_prefixes": [],
        },
        "ci": {"hadolint": False, "vscode_required": True},
    }


def ensure_project_config(path: Path = DEFAULT_PROJECT_CONFIG_PATH) -> None:
    if not path.exists():
        _dump_yaml(path, default_config_dict())


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(
    project_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Load merged config with deep merge: defaults <- global <- project."""
    project_cfg_path = (project_path or Path.cwd()) / DEFAULT_PROJECT_CONFIG_PATH
    global_cfg = _load_yaml(DEFAULT_GLOBAL_CONFIG_PATH)
    project_cfg = _load_yaml(project_cfg_path)

    cfg = default_config_dict()
    if isinstance(global_cfg, dict):
        _deep_merge(cfg, global_cfg)
    if isinstance(project_cfg, dict):
        _deep_merge(cfg, project_cfg)
    return cfg


def human_summary(cfg: Dict[str, Any]) -> str:
    mode = cfg.get("performance", {}).get("mode", "fast")
    on_save = cfg["performance"]["on_save"]
    on_commit = cfg["performance"]["on_commit"]
    on_push = cfg["performance"]["on_push"]
    return (
        f"Mode: {mode}\n"
        f"On Save: format={on_save['format_on_save']}, lint_changed_only={on_save['lint_changed_only']}, "
        f"typecheck_incremental={on_save['typecheck_incremental']}, quick_tests={on_save['quick_tests']}\n"
        f"On Commit: lint={on_commit['lint']}, typecheck_incremental={on_commit['typecheck_incremental']}, "
        f"test_impacted={on_commit['test_impacted']}\n"
        f"On Push: test_all={on_push['test_all']}, coverage.enforce={on_push['coverage']['enforce']}, "
        f"min_module={on_push['coverage']['min_module']}, security_scan={on_push['security_scan']}, "
        f"mutation_test={on_push['mutation_test']}\n"
    )


# ---- Typed accessors to reduce deep dict coupling ----


def get_min_module(cfg: Dict[str, Any], default: float = 0.9) -> float:
    perf = (
        cfg.get("performance", {})
        if isinstance(cfg.get("performance", {}), dict)
        else {}
    )
    return float(
        ((perf.get("on_push", {}) or {}).get("coverage", {}) or {}).get(
            "min_module", default
        )
    )


def get_coverage_policy(cfg: Dict[str, Any]) -> Optional[Dict[str, float]]:
    cov = cfg.get("coverage", {})
    if isinstance(cov, dict):
        pol = cov.get("policy")
        if pol is None:
            return None
        if isinstance(pol, dict):
            # best-effort cast to Dict[str, float]
            out: Dict[str, float] = {}
            for k, v in pol.items():
                try:
                    out[str(k)] = float(v)
                except Exception:
                    continue
            return out
    return None
