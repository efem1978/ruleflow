from __future__ import annotations

import os
from pathlib import Path

import mcp_rules_assistant.license_utils as lu


def test_verify_ed25519_wrong_pubkey_type_returns_false(monkeypatch):
    # Provide an RSA public key while calling ed25519 verifier → should return False
    rsa_pub = (
        "-----BEGIN PUBLIC KEY-----\n"
        "MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBALTKUxu9tTbmq3v1Ecic9kCq1NHWwWQn\n"
        "qUF+Z8F2qVvm1m9+9bE1q1zw6j+M0Xz8cESjFf7QdF4KfWcQqZzq4wECAwEAAQ==\n"
        "-----END PUBLIC KEY-----\n"
    )
    monkeypatch.setenv("MCP_LICENSE_ED25519_PUBKEY", rsa_pub)
    assert lu._verify_ed25519(b"payload", "AA") is False


def test_generate_license_ed25519_with_rsa_key_raises_runtimeerror(tmp_path: Path):
    # Using RSA private key for ed25519 signing should raise RuntimeError
    rsa_priv = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIBOgIBAAJBAK0ylF7hTHcC2mWH01hjZva8r4m1qkZPh1wE7RkK2N4u3P8VjKCY\n"
        "k0qSIfHqp2qgqU2bYy1b9c7wP7lYfV1Q0/sCAwEAAQJAFg2wz9t0o2z7cSlN1q6q\n"
        "z6l8q4xJmT8L3l2mFc5kRt1tq0Q8qm3cO1iYz7hQ7hGqXn6G6eEvmKjzDE6YkN2+\n"
        "UQIhAOoP8w5X4T1GmJkM+6pZV8bP9o3u4m8pK0a9lXc2SeiVAiEAu7oFQF6fL8wz\n"
        "kAvcPLaMM6g7ctf2zQvBqBzZyicVxV8CIQC19gqYv5r7oZIv4X1jeXxX3cJ1a8p9\n"
        "b/YJ4k7cVZfoYwIgH1R7XcJ2sR3pH3TQ6HkqTphJc0mK+QACQ0cI9bV6l2UCIQCK\n"
        "3m1rli8O562p1v3a1+3M2T0S9eN1m7eomZ3k7vX7l6mFZw==\n"
        "-----END RSA PRIVATE KEY-----\n"
    ).encode("utf-8")
    try:
        lu.generate_license(
            issued_to="Alice",
            expires="2030-01-01",
            machine="",
            alg="ed25519",
            private_key_pem=rsa_priv,
        )
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "ed25519 signing failed" in str(e)
