from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_rules_assistant.license_utils import generate_license, verify_license


def test_verify_missing_file(tmp_path: Path) -> None:
    p = tmp_path / "license.json"
    res = verify_license(p)
    assert res["ok"] is False and res["activated"] is False


def test_verify_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / "license.json"
    p.write_text("{ not: json }", encoding="utf-8")
    res = verify_license(p)
    assert res["ok"] is False and res["activated"] is False


def test_generate_hs256_and_verify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Use a deterministic salt for reproducibility
    monkeypatch.setenv("MCP_LICENSE_SALT", "test-salt")
    lic = generate_license(
        issued_to="Alice",
        expires="2099-01-01",
        machine="node-1",
        alg="hs256",
    )
    p = tmp_path / "license.json"
    p.write_text(json.dumps(lic), encoding="utf-8")
    res = verify_license(p)
    assert res["activated"] is True
    assert res["ok"] is True
    assert res["date_ok"] is True
    assert res["signature_ok"] is True


def test_generate_rs256_requires_private_key() -> None:
    with pytest.raises(ValueError):
        generate_license(
            issued_to="A",
            expires="2099-01-01",
            machine="",
            alg="rs256",
        )


def test_verify_rs256_without_pubkey(tmp_path: Path) -> None:
    # No pubkey in env -> rs256 signature check fails; should report activated True but ok False
    lic = {
        "issued_to": "Bob",
        "expires": "2099-01-01",
        "machine": "",
        "alg": "rs256",
        "signature": "deadbeef",
    }
    p = tmp_path / "license.json"
    p.write_text(json.dumps(lic), encoding="utf-8")
    res = verify_license(p)
    assert res["activated"] is True
    assert res["ok"] is False
    assert res["signature_ok"] is False
    assert res["date_ok"] is True


def test_verify_invalid_expires_formats(tmp_path: Path) -> None:
    lic = {
        "issued_to": "Carol",
        "expires": "20-01-01",
        "machine": "",
        "alg": "hs256",
        "signature": "",
    }
    p = tmp_path / "license.json"
    p.write_text(json.dumps(lic), encoding="utf-8")
    res = verify_license(p)
    assert res["activated"] is True
    assert res["date_ok"] is False
    assert res["ok"] is False
