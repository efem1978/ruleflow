from __future__ import annotations

import json
from pathlib import Path

import pytest

# Skip all tests in this module if cryptography is not available
pytest.importorskip("cryptography")

from mcp_rules_assistant.license_utils import generate_license, verify_license


def _gen_ed25519_keypair() -> tuple[bytes, bytes]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv = Ed25519PrivateKey.generate()
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub = priv.public_key()
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return priv_pem, pub_pem


def test_generate_and_verify_ed25519(tmp_path: Path, monkeypatch) -> None:
    priv_pem, pub_pem = _gen_ed25519_keypair()
    monkeypatch.setenv("MCP_LICENSE_ED25519_PUBKEY", pub_pem.decode("utf-8"))
    lic = generate_license(
        issued_to="tester@example.com",
        expires="2099-12-31",
        machine="node-1",
        alg="ed25519",
        private_key_pem=priv_pem,
    )
    p = tmp_path / "license.json"
    p.write_text(json.dumps(lic), encoding="utf-8")
    res = verify_license(p)
    assert res.get("ok") is True
    assert res.get("alg") == "ed25519"
    assert res.get("signature_ok") is True
    assert res.get("date_ok") is True


def test_verify_ed25519_signature_mismatch(tmp_path: Path, monkeypatch) -> None:
    priv_pem, pub_pem = _gen_ed25519_keypair()
    monkeypatch.setenv("MCP_LICENSE_ED25519_PUBKEY", pub_pem.decode("utf-8"))
    lic = generate_license(
        issued_to="tester2@example.com",
        expires="2099-12-31",
        machine="node-2",
        alg="ed25519",
        private_key_pem=priv_pem,
    )
    # Corrupt signature
    lic["signature"] = "AA" + lic["signature"]
    p = tmp_path / "license.json"
    p.write_text(json.dumps(lic), encoding="utf-8")
    res = verify_license(p)
    assert res.get("ok") is False
    assert res.get("signature_ok") is False
