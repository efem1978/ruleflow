from __future__ import annotations

from pathlib import Path

import yaml

from mcp_rules_assistant.mcp_server import JsonRpcServer


def _tool(name: str, args: dict | None = None) -> dict:
    srv = JsonRpcServer()
    return srv._call_tool(name, args or {})


def test_fs_apply_patch_disallow_flag_parse_exception(
    tmp_path: Path, monkeypatch
) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # config: disallow_patterns present; enable strict mode
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    cfg = {"execution": {"disallow_patterns": ["FORBIDDEN"]}}
    (tmp_path / ".mcp/assistant.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    # make _get_exec_flag raise to cover except path setting hard_gate=False
    monkeypatch.setattr(
        srv, "_get_exec_flag", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
    )
    out = srv._call_tool(
        "fs.apply_patch",
        {
            "files": [
                {"path": "mcp_rules_assistant/x.py", "content": "print('FORBIDDEN')"}
            ],
            "runChecks": False,
            "strict": True,
        },
    )
    assert out.get("ok") is True


def test_resources_list_handles_glob_exception(tmp_path: Path, monkeypatch) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # monkeypatch Path.glob to raise when called on .mcp dir
    from pathlib import Path as _P

    orig_glob = _P.glob

    def bad_glob(self, pattern):  # type: ignore[override]
        if str(self).endswith("/.mcp"):
            raise RuntimeError("boom")
        return orig_glob(self, pattern)

    monkeypatch.setattr(_P, "glob", bad_glob)
    r = srv.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}}
    )
    assert "resources" in r.get("result", {})
