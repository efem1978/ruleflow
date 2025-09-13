from __future__ import annotations

import os
from pathlib import Path

import pytest

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_fs_apply_patch_rejects_symlink(tmp_path: Path) -> None:
    # 某些平台（或权限）可能不支持创建符号链接；如失败则跳过本用例
    target = tmp_path / "real.py"
    target.write_text("print('x')\n", encoding="utf-8")
    link = tmp_path / "link.py"
    try:
        if hasattr(os, "symlink"):
            os.symlink(target, link)
        else:  # pragma: no cover - 非 POSIX 平台
            pytest.skip("symlink not supported on this platform")
    except OSError:
        pytest.skip("symlink creation not permitted")

    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # patch Path.is_symlink 以覆盖“解析后仍被视为符号链接”的防御分支
    from pathlib import Path as _P

    orig_is_symlink = _P.is_symlink

    def fake_is_symlink(self):  # noqa: ANN001
        # 解析后得到的 real.py 也被视为符号链接，从而触发拒绝写入分支
        if str(self).endswith("/real.py"):
            return True
        return orig_is_symlink(self)

    import builtins

    try:
        setattr(_P, "is_symlink", fake_is_symlink)
        with pytest.raises(ValueError):
            srv._call_tool(
                "fs.apply_patch",
                {
                    "files": [{"path": "link.py", "content": "print('y')\n"}],
                    "runChecks": False,
                },
            )
    finally:
        setattr(_P, "is_symlink", orig_is_symlink)
