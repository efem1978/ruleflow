from __future__ import annotations

from pathlib import Path

from mcp_rules_assistant.license_utils import generate_license, verify_license


def test_verify_ed25519_no_pubkey(tmp_path: Path) -> None:
    # Prepare a license with alg=ed25519 but without pubkey env → signature_ok=False
    lic = {
        "issued_to": "Alice",
        "expires": "2099-01-01",
        "machine": "",
        "alg": "ed25519",
        "signature": "abcd",  # not a valid signature
    }
    p = tmp_path / "license.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(__import__("json").dumps(lic), encoding="utf-8")
    out = verify_license(path=p)
    assert out["activated"] is True
    assert out["alg"] == "ed25519"
    # No pubkey in env → ed25519 verify returns False
    assert out["signature_ok"] is False
    # date is valid in far future
    assert out["date_ok"] is True
    assert out["ok"] is False


def test_generate_license_ed25519_requires_private_key() -> None:
    # Missing private key for ed25519 should raise
    try:
        generate_license(issued_to="A", expires="2099-01-01", machine="", alg="ed25519")
        raise AssertionError("expected ValueError for missing private key")
    except ValueError as e:
        assert "private key" in str(e)


def test_verify_ed25519_wrong_key_type_env(tmp_path: Path, monkeypatch) -> None:
    # Set ED25519 pubkey env to an RSA public key → type mismatch → signature_ok=False
    rsa_pub_pem = (
        "-----BEGIN PUBLIC KEY-----\n"
        "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwF1kqF5D/8v0Hn10OQwT\n"
        "u1nq7r1sQqZp4mB0p3V0wW4u9H3W6Q9Q+0D9R2kP5Q+3r9F7qjC6zYl8T5l3xwA9\n"
        "s5r6O2c3b5bVwM1N1Hc5aJmJ7L1b1bXv2m1k5B1FQH8W3F2q2r6sZ6WcV3Q9Fh1K\n"
        "2h5JQy6c9w7r1x2y3z4A5B6C7D8E9F0G1H2I3J4K5L6M7N8O9P0Q1R2S3T4U5V6W\n"
        "X7Y8Z9aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpPqQrRsStTuUvVwWxXyYzZ0\n"
        "IDAQAB\n"
        "-----END PUBLIC KEY-----\n"
    )
    monkeypatch.setenv("MCP_LICENSE_ED25519_PUBKEY", rsa_pub_pem)

    lic = {
        "issued_to": "Alice",
        "expires": "2099-01-01",
        "machine": "",
        "alg": "ed25519",
        "signature": "abcd",
    }
    p = tmp_path / "license.json"
    p.write_text(__import__("json").dumps(lic), encoding="utf-8")
    out = verify_license(path=p)
    assert out["alg"] == "ed25519"
    # Wrong key type in env → loader returns RSA key, type mismatch branch returns False
    assert out["signature_ok"] is False
    assert out["ok"] is False
