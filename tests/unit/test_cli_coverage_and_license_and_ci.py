from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mcp_rules_assistant.cli import app


def _runner() -> CliRunner:
    return CliRunner()


def test_cli_license_activate_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # isolate HOME and CWD
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    # invoke with a non-existing file
    r = _runner().invoke(app, ["license-activate", "--file", "nope.json"])
    assert r.exit_code != 0
    assert "license file not found" in r.stdout


def test_cli_license_verify_prints_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    # no license.json -> activated False
    r = _runner().invoke(app, ["license-verify"])
    assert r.exit_code == 0
    assert "activated" in r.stdout


def test_cli_license_generate_prints_when_no_out(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCP_LICENSE_SALT", "test-salt")
    r = _runner().invoke(
        app,
        [
            "license-generate",
            "--issued-to",
            "Alice",
            "--expires",
            "2099-01-01",
            "--alg",
            "hs256",
        ],
    )
    assert r.exit_code == 0
    # output contains JSON text
    assert "issued_to" in r.stdout


def test_cli_license_generate_rs256_requires_key(tmp_path: Path) -> None:
    r = _runner().invoke(
        app,
        [
            "license-generate",
            "--issued-to",
            "Org",
            "--expires",
            "2099-01-01",
            "--alg",
            "rs256",
        ],
    )
    assert r.exit_code != 0
    assert "--private-key required" in r.stdout


def test_cli_license_generate_rs256_missing_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    r = _runner().invoke(
        app,
        [
            "license-generate",
            "--issued-to",
            "Org",
            "--expires",
            "2099-01-01",
            "--alg",
            "rs256",
            "--private-key",
            "no-key.pem",
        ],
    )
    assert r.exit_code != 0
    assert "private key not found" in r.stdout


def test_cli_license_generate_out_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    r = _runner().invoke(
        app,
        [
            "license-generate",
            "--issued-to",
            "Alice",
            "--expires",
            "2099-01-01",
            "--alg",
            "hs256",
            "--out",
            "lic.json",
        ],
    )
    assert r.exit_code == 0
    assert Path("lic.json").exists()


def test_cli_precommit_migrate_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    r = _runner().invoke(app, ["precommit-migrate-stages"])
    assert r.exit_code != 0
    assert ".pre-commit-config.yaml not found" in r.stdout


def test_cli_precommit_migrate_parse_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    Path(".pre-commit-config.yaml").write_text(": {", encoding="utf-8")
    r = _runner().invoke(app, ["precommit-migrate-stages"])
    assert r.exit_code != 0
    assert "yaml parse error" in r.stdout


def test_cli_precommit_migrate_changes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    data = {
        "repos": [
            {
                "repo": "local",
                "hooks": [
                    {"id": "x", "stages": ["commit", "push"]},
                    {"id": "y", "stages": ["commit"]},
                ],
            }
        ]
    }
    Path(".pre-commit-config.yaml").write_text(
        __import__("yaml").safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    r = _runner().invoke(app, ["precommit-migrate-stages"])
    assert r.exit_code == 0
    # output is Python dict string; perform a loose check
    assert "changed" in r.stdout and "True" in r.stdout


def test_cli_precommit_migrate_else_branch_kept(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    data = {"repos": [{"repo": "local", "hooks": [{"id": "x", "stages": ["lint"]}]}]}
    Path(".pre-commit-config.yaml").write_text(
        __import__("yaml").safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    r = _runner().invoke(app, ["precommit-migrate-stages"])
    assert r.exit_code == 0
    # unchanged
    assert "changed" in r.stdout and "False" in r.stdout


def test_cli_rules_suggestions_text_else_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # prepare compiled suggestions with one item missing 'value' to trigger the else branch
    monkeypatch.chdir(tmp_path)
    cdir = tmp_path / ".mcp"
    cdir.mkdir(parents=True, exist_ok=True)
    payload = {"suggestions": [{"key": "a", "action": "set", "severity": "info"}]}
    (cdir / "rules_compiled.json").write_text(json.dumps(payload), encoding="utf-8")
    r = _runner().invoke(app, ["rules-suggestions", "--format", "text"])
    assert r.exit_code == 0
    # Some renderers may drop the severity label; accept both variants
    assert ("[info] a (set)" in r.stdout) or ("  a (set)" in r.stdout)


def test_cli_ci_set_yaml_parse_error_then_update(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # invalid YAML -> except branch; still proceed to write ci fields
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(": {", encoding="utf-8")
    r = _runner().invoke(app, ["ci-set", "--hadolint"])  # sets to True
    assert r.exit_code == 0
    assert "CI 配置已更新" in r.stdout


def test_cli_coverage_near_set_yaml_parse_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / ".mcp/assistant.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("not: yaml: here: [", encoding="utf-8")
    r = _runner().invoke(app, ["coverage-near-set", "--within", "5", "--top", "10"])  # type: ignore[arg-type]
    assert r.exit_code == 0
    assert "near" in r.stdout
