from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.mcp_server import JsonRpcServer


def test_fs_apply_patch_exec_flag_parse_exception(tmp_path: Path, monkeypatch) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path

    # 构造一个 cfg 对象：第一次 get() 返回 dict（用于 exec_cfg_eff），第二次 get() 抛异常
    class Cfg:
        def __init__(self):
            self._exec_calls = 0

        def get(self, key, default=None):  # noqa: ANN001
            # 前两次获取 execution 返回 dict；第三次获取 execution 抛异常（落入 except 分支）
            if key == "execution":
                self._exec_calls += 1
                if self._exec_calls >= 3:
                    raise RuntimeError("cfg.get boom")
                return {}
            return {}

    srv.cfg = Cfg()  # type: ignore[assignment]

    def boom(*_a, **_k):  # noqa: ANN001
        raise RuntimeError("flag parse error")

    monkeypatch.setattr(srv, "_get_exec_flag", boom, raising=True)
    out = srv._call_tool(
        "fs.apply_patch",
        {
            "files": [{"path": "x.py", "content": "print(1)\n"}],
            "runChecks": False,
            "dryRun": True,
        },
    )
    assert out.get("ok") is True
