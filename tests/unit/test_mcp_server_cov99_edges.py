from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_rules_assistant.license_utils import generate_license
from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict) -> dict:
    return {"jsonrpc": "2.0", "id": "1", "method": method, "params": params}


def test_ci_validate_ok_with_project_license_hs256(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    mcp = tmp_path / ".mcp"
    mcp.mkdir(parents=True, exist_ok=True)
    # enable license.required
    (mcp / "assistant.yaml").write_text(
        "license:\n  required: true\n", encoding="utf-8",
    )
    # write a valid hs256 license into project scope
    lic = generate_license(issued_to="Alice", expires="2099-01-01", machine="")
    (mcp / "license.json").write_text(json.dumps(lic), encoding="utf-8")
    # call ci.validate → should pass and exercise project-scoped verify branch
    out = srv._call_tool("ci.validate", {})
    assert out.get("ok") is True


def test_ci_validate_gate_verify_raises_and_json_dump_fail(
    tmp_path: Path, monkeypatch,
) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    mcp = tmp_path / ".mcp"
    mcp.mkdir(parents=True, exist_ok=True)
    # enable license.required (but no project license file)
    (mcp / "assistant.yaml").write_text(
        "license:\n  required: true\n", encoding="utf-8",
    )
    # force _verify_license to raise, and json.dumps to raise when writing summary json
    import mcp_rules_assistant.mcp_server as ms

    monkeypatch.setattr(
        ms,
        "_verify_license",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(
        ms.json, "dumps", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("dump")),
    )
    with pytest.raises(Exception):
        srv._call_tool("ci.validate", {})
    # release_check.md should still be written (json failed but md write succeeded)
    assert (mcp / "dashboard" / "release_check.md").exists()


def test_ci_validate_success_json_dump_fail(tmp_path: Path, monkeypatch) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # ensure json.dumps fails on success-path summary write
    import mcp_rules_assistant.mcp_server as ms

    monkeypatch.setattr(
        ms.json, "dumps", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("dump")),
    )
    out = srv._call_tool("ci.validate", {})
    assert out.get("ok") is True


def test_fs_apply_patch_disallow_hardflag_parse_exception(
    tmp_path: Path, monkeypatch,
) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    # configure patterns and force _get_exec_flag to raise when asked for hard gate
    srv.cfg.setdefault("execution", {})["disallow_patterns"] = ["BAD"]

    def _raise_on_hard(key: str, default: object) -> object:
        if key == "disallow_patterns_hard":
            raise RuntimeError("flag parse error")
        return default

    monkeypatch.setattr(srv, "_get_exec_flag", _raise_on_hard)
    # dryRun to avoid real writes; include content triggering the pattern path
    out = srv._call_tool(
        "fs.apply_patch",
        {"files": [{"path": "a.py", "content": "# BAD content"}], "dryRun": True},
    )
    assert out.get("ok") is True


def test_res_read_memory_ns_parse_exception(tmp_path: Path) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path

    class Bad:
        def __str__(self) -> str:  # type: ignore[override]
            raise RuntimeError("no str")

    out = srv._res_read_memory(Bad())  # type: ignore[arg-type]
    assert out.get("mimeType") == "application/json"
    assert "turns" in json.loads(out.get("text") or "{}")


def test_coverage_export_delta_calc_exception(tmp_path: Path, monkeypatch) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    out_dir = tmp_path / "out"
    import mcp_rules_assistant.mcp_server as ms

    # monkeypatch coverage summary functions to craft bad numeric types
    class RaiseOnFloat:
        def __float__(self) -> float:  # type: ignore[override]
            raise ValueError("bad")

    class FakeItem(dict):
        def __init__(self) -> None:
            super().__init__({"file": "x", "coverage": 0.8, "threshold": 0.9})
            self._first = True

        def get(self, k: str, default=None):  # type: ignore[override]
            if k == "threshold" and self._first:
                self._first = False
                return RaiseOnFloat()
            return super().get(k, default)

    monkeypatch.setattr(
        ms.covsum, "summarize", lambda **kw: {"ok": True, "weak": [FakeItem()]},
    )
    monkeypatch.setattr(ms.covsum, "summarize_groups", lambda **kw: {"groups": []})
    monkeypatch.setattr(ms.covsum, "summarize_near", lambda **kw: {"near": []})
    res = srv._tool_coverage_export(
        {"outDir": str(out_dir), "weakTop": 5, "nearTop": 5},
    )
    assert res.get("ok") is True
    # files generated
    assert (out_dir / "coverage_summary.json").exists()
    assert (out_dir / "weak_top.csv").exists()
    assert (out_dir / "near_top.csv").exists()
    assert (out_dir / "groups.csv").exists()


def test_config_update_license_gate_parse_exception(
    tmp_path: Path, monkeypatch,
) -> None:
    srv = JsonRpcServer()
    srv.project_root = tmp_path
    (tmp_path / ".mcp").mkdir(parents=True, exist_ok=True)
    # enable license.required in config file
    (tmp_path / ".mcp/assistant.yaml").write_text(
        "license:\n  required: true\n", encoding="utf-8",
    )

    def _boom() -> bool:
        raise RuntimeError("boom")

    # touched keys present and _license_required raises → parse exception path covered
    monkeypatch.setattr(srv, "_license_required", _boom)
    out = srv._call_tool(
        "config.update",
        {"data": {"hadolint": True}},
    )
    assert out.get("ok") is True
