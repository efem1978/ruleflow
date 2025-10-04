from __future__ import annotations

import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from mcp_rules_assistant.license_utils import generate_license, verify_license


def _gen_keys():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pri = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return pri, pub


def test_generate_and_verify_rs256(tmp_path: Path, monkeypatch) -> None:
    pri, pub = _gen_keys()
    lic = generate_license(
        issued_to="Org",
        expires="2099-01-01",
        machine="host",
        alg="rs256",
        private_key_pem=pri,
    )
    p = tmp_path / "license.json"
    p.write_text(json.dumps(lic), encoding="utf-8")
    monkeypatch.setenv("MCP_LICENSE_PUBKEY", pub.decode("utf-8"))
    res = verify_license(p)
    assert res["ok"] is True and res["signature_ok"] is True and res["date_ok"] is True
