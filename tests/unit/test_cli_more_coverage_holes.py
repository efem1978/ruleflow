from __future__ import annotations

import json
import runpy
from pathlib import Path

from typer.testing import CliRunner

import mcp_rules_assistant.cli as cli
from mcp_rules_assistant.cli import app


def test_cli_ide_scaffold_unsupported_editor(tmp_path: Path) -> None:
    r = CliRunner().invoke(
        app, ["ide-scaffold", "--editor", "unknown"], env={"PYTHONPATH": str(tmp_path)}
    )
    assert r.exit_code != 0 and "unsupported editor" in (r.stdout or "")


def test_cli_license_generate_rs256_happy(tmp_path: Path) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    kpath = tmp_path / "priv.pem"
    kpath.write_text(pem.decode("utf-8"), encoding="utf-8")
    r = CliRunner().invoke(
        app,
        [
            "license-generate",
            "--issued-to",
            "A",
            "--expires",
            "2099-01-01",
            "--alg",
            "rs256",
            "--private-key",
            str(kpath),
            "--out",
            str(tmp_path / "lic.json"),
        ],
    )
    assert r.exit_code == 0 and (tmp_path / "lic.json").exists()


def test_cli_diagnose_writable_suggestion(tmp_path: Path, monkeypatch) -> None:
    # force os.access to return False so suggestion for writable paths is added
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        monkeypatch.setattr(cli.os, "access", lambda *a, **k: False)
        out = runner.invoke(app, ["diagnose", "--json"]).stdout
        d = json.loads(out)
        sugg = d.get("suggestions") or []
        # should include writable hint
        assert any("不可写" in s or "writable" in s for s in sugg)


def test_cli_plan_tasks_ignore_code_fences(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".mcp").mkdir(parents=True, exist_ok=True)
        Path(".mcp/plan.md").write_text(
            """# 项目计划 / Project Plan\n- 状态: planned\n- 当前步骤: a\n- 下一步: b\n\n```\n- [ ] should be ignored inside code\n- [x] also ignored\n```\n- [ ] legit pending\n- [x] legit done\n""",
            encoding="utf-8",
        )
        r = runner.invoke(app, ["plan-tasks", "--json"])
        d = json.loads(r.stdout or "{}")
        assert "should be ignored" not in json.dumps(d)
        assert any("legit pending" in x for x in d.get("pending", []))
        assert any("legit done" in x for x in d.get("done", []))


def test_cli_rules_onboard_apply_parse_error(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create invalid YAML to hit parse except path when applying
        Path(".mcp").mkdir(parents=True, exist_ok=True)
        Path(".mcp/assistant.yaml").write_text(": {", encoding="utf-8")
        r = runner.invoke(
            app,
            [
                "rules-onboard",
                "--scenario",
                "personal",
                "--complexity",
                "small",
                "--dev-mode",
                "tdd",
                "--apply",
            ],
        )
        assert r.exit_code == 0


def test_cli_rules_export_stdout_paths(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Prepare compiled files
        Path(".mcp").mkdir(parents=True, exist_ok=True)
        (Path(".mcp/rules_compiled.json")).write_text("{}", encoding="utf-8")
        (Path(".mcp/rules_compiled.md")).write_text("# md", encoding="utf-8")
        (Path(".mcp/rules_suggestions.md")).write_text("# sugg", encoding="utf-8")
        r = runner.invoke(app, ["rules-export"])  # stdout mode
        assert r.exit_code == 0
        out = r.stdout or ""
        assert "Compiled Rules" in out and "Suggestions" in out


def test_cli_cleanup_no_artifacts(tmp_path: Path) -> None:
    # Ensure --no-artifacts runs and prints empty removed list
    out = CliRunner().invoke(app, ["cleanup", "--no-artifacts"]).stdout
    assert "removed" in out
