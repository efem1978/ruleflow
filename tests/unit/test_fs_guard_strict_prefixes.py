from __future__ import annotations

from pathlib import Path

import pytest

from mcp_rules_assistant.fs_wrapper import FSGuard


def test_fs_guard_strict_prefix_block(tmp_path: Path) -> None:
    # configure allowed prefix to 'src/' only; writing to 'docs/x.txt' should fail in strict mode
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    guard = FSGuard(tmp_path)
    guard.cfg.setdefault("execution", {})["allowed_write_prefixes"] = ["src/"]
    guard.cfg["execution"]["fs_guard_strict"] = True
    with pytest.raises(Exception):
        guard.write_text(Path("docs/x.txt"), "hello")
