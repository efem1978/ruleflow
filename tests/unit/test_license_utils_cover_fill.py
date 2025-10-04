from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mcp_rules_assistant.license_utils import generate_license, verify_license


def test_generate_missing_required_fields() -> None:
    # missing issued_to
    with pytest.raises(ValueError):
        generate_license(issued_to="", expires="2099-01-01", machine="host")
    # missing expires
    with pytest.raises(ValueError):
        generate_license(issued_to="A", expires="", machine="host")


def test_generate_invalid_expires_format() -> None:
    with pytest.raises(ValueError):
        generate_license(issued_to="A", expires="2099/01/01", machine="host")


def test_verify_hs256_sha256_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Prepare a valid hs256 payload then monkeypatch hashlib.sha256 to raise
    lic = generate_license(issued_to="B", expires="2099-01-01", machine="m")
    p = tmp_path / "lic.json"
    p.write_text(json.dumps(lic), encoding="utf-8")

    class _Err:
        def __call__(self, *a: Any, **k: Any) -> Any:  # noqa: ANN401
            raise RuntimeError("boom")

    import mcp_rules_assistant.license_utils as LU

    monkeypatch.setattr(LU.hashlib, "sha256", _Err())
    res = verify_license(p)
    # Outer except should set signature_ok False, ok False, but activated True
    assert (
        res["activated"] is True and res["ok"] is False and res["signature_ok"] is False
    )


def test_verify_rs256_malformed_pubkey_triggers_internal_except(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Create an rs256 license, then feed a malformed public key to trigger _verify_rs256 except path
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pri = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    lic = generate_license(
        issued_to="Org",
        expires="2099-01-01",
        machine="z",
        alg="rs256",
        private_key_pem=pri,
    )
    p = tmp_path / "license.json"
    p.write_text(json.dumps(lic), encoding="utf-8")

    # Malformed PEM (not a PEM at all) → load_pem_public_key raises → _verify_rs256 except path
    monkeypatch.setenv("MCP_LICENSE_PUBKEY", "NOT_A_PEM")
    res = verify_license(p)
    assert (
        res["activated"] is True and res["ok"] is False and res["signature_ok"] is False
    )
