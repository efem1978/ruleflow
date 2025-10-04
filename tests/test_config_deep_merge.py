from __future__ import annotations

import os
from pathlib import Path

from mcp_rules_assistant.config import load_config


def chdir(path: Path):
    class _Ctx:
        def __enter__(self):
            self._old = Path.cwd()
            os.chdir(path)
            return path

        def __exit__(self, exc_type, exc, tb):
            os.chdir(self._old)

    return _Ctx()


def test_load_config_deep_merge_preserves_nested_defaults(tmp_path: Path) -> None:
    with chdir(tmp_path):
        (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".mcp/assistant.yaml").write_text(
            "\n".join(
                [
                    "performance:",
                    "  on_push:",
                    "    coverage: { min_module: 0.93 }",
                ],
            ),
            encoding="utf-8",
        )
        cfg = load_config()
        # deep fields remain
        assert cfg["performance"]["on_push"]["test_all"] is True
        assert cfg["performance"]["on_push"]["security_scan"] is True
        # coverage.min_core preserved
        assert (
            abs(float(cfg["performance"]["on_push"]["coverage"]["min_core"]) - 0.95)
            < 1e-6
        )
        # overridden min_module applied
        assert (
            abs(float(cfg["performance"]["on_push"]["coverage"]["min_module"]) - 0.93)
            < 1e-6
        )
