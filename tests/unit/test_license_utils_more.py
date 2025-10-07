from __future__ import annotations

import json
from pathlib import Path

import pytest

# Skip all tests in this module if cryptography is not available
cryptography = pytest.importorskip("cryptography")
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from mcp_rules_assistant.license_utils import generate_license, verify_license


def _gen_rsa_keys():
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


def test_verify_rs256_with_non_rsa_pubkey(tmp_path: Path, monkeypatch) -> None:
    pri, _ = _gen_rsa_keys()
    lic = generate_license(
        issued_to="X",
        expires="2099-01-01",
        machine="",
        alg="rs256",
        private_key_pem=pri,
    )
    # 使用 EC 公钥，触发非 RSA 分支 -> signature_ok False
    eckey = ec.generate_private_key(ec.SECP256R1())
    pub = eckey.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setenv("MCP_LICENSE_PUBKEY", pub.decode("utf-8"))
    p = tmp_path / "license.json"
    p.write_text(json.dumps(lic), encoding="utf-8")
    res = verify_license(p)
    assert res["activated"] is True
    assert res["ok"] is False and res["signature_ok"] is False


def test_generate_rs256_with_non_rsa_private_key_raises() -> None:
    eckey = ec.generate_private_key(ec.SECP256R1())
    pem = eckey.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with pytest.raises(RuntimeError):
        generate_license(
            issued_to="Y",
            expires="2099-01-01",
            machine="",
            alg="rs256",
            private_key_pem=pem,
        )


def test_verify_hs256_signature_mismatch(tmp_path: Path) -> None:
    lic = generate_license(issued_to="Z", expires="2099-01-01", machine="", alg="hs256")
    # 伪造错误签名
    lic_bad = dict(lic)
    lic_bad["signature"] = "deadbeef"
    p = tmp_path / "lic.json"
    p.write_text(json.dumps(lic_bad), encoding="utf-8")
    res = verify_license(p)
    assert res["activated"] is True
    assert (
        res["ok"] is False and res["signature_ok"] is False and res["date_ok"] is True
    )
