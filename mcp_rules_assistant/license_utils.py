from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

LICENSE_PATH = Path.home() / ".mcp/license.json"
# 说明：SALT 为对称验签演示；生产建议首选非对称验签（RS256/ECDSA）
_SALT = os.environ.get("MCP_LICENSE_SALT", "mcp-demo-salt-202409")
_PUBKEY_ENV = "MCP_LICENSE_PUBKEY"  # PEM (RSA) in environment


def _read_license(path: Path = LICENSE_PATH) -> Tuple[Dict[str, Any], bool]:
    if not path.exists():
        return {}, False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}, True
    except Exception:
        return {}, False


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _verify_rs256(payload: bytes, signature_b64: str) -> bool:
    pem = os.environ.get(_PUBKEY_ENV, "").strip()
    if not pem:
        return False
    try:
        from cryptography.hazmat.primitives import hashes  # type: ignore[import-not-found]
        from cryptography.hazmat.primitives.asymmetric import padding  # type: ignore[import-not-found]
        from cryptography.hazmat.primitives.serialization import load_pem_public_key  # type: ignore[import-not-found]

        pub = load_pem_public_key(pem.encode("utf-8"))
        sig = _b64url_decode(signature_b64)
        pub.verify(sig, payload, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def verify_license(path: Path = LICENSE_PATH) -> Dict[str, Any]:
    data, exists = _read_license(path)
    if not exists:
        return {"ok": False, "activated": False, "reason": "license file missing"}
    issued_to = str(data.get("issued_to", "")).strip()
    expires = str(data.get("expires", "")).strip()  # yyyy-mm-dd
    machine = str(data.get("machine", "")).strip()
    signature = str(data.get("signature", "")).strip()
    alg = str(data.get("alg", "hs256") or "hs256").lower()
    now = datetime.utcnow().date()
    valid_date = True
    if expires:
        try:
            valid_date = now <= datetime.strptime(expires, "%Y-%m-%d").date()
        except Exception:
            valid_date = False
    # 验签：优先按 alg=rs256（如配置了公钥），否则按 hs256（SALT 演示）
    sig_ok = False
    try:
        if alg == "rs256":
            payload = f"{issued_to}|{expires}|{machine}".encode("utf-8")
            sig_ok = _verify_rs256(payload, signature)
        else:
            raw = f"{issued_to}|{expires}|{machine}|{_SALT}".encode("utf-8")
            calc = hashlib.sha256(raw).hexdigest()
            sig_ok = bool(signature and signature.lower() == calc)
    except Exception:
        sig_ok = False
    return {
        "ok": bool(sig_ok and valid_date),
        "activated": True,
        "issued_to": issued_to,
        "expires": expires,
        "machine": machine,
        "signature_ok": sig_ok,
        "date_ok": valid_date,
        "alg": alg,
    }


def _sign_rs256(payload: bytes, private_key_pem: bytes) -> str:
    try:
        from cryptography.hazmat.primitives import hashes  # type: ignore[import-not-found]
        from cryptography.hazmat.primitives.asymmetric import padding  # type: ignore[import-not-found]
        from cryptography.hazmat.primitives.serialization import load_pem_private_key  # type: ignore[import-not-found]

        key = load_pem_private_key(private_key_pem, password=None)
        sig = key.sign(payload, padding.PKCS1v15(), hashes.SHA256())
        return base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")
    except Exception as e:  # pragma: no cover - depends on optional crypto
        raise RuntimeError(f"rs256 signing failed: {e}")


def generate_license(
    *,
    issued_to: str,
    expires: str,
    machine: str,
    alg: str = "hs256",
    private_key_pem: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Generate a license dict with signature.

    - alg=hs256 uses SALT-based sha256 hex (demo).
    - alg=rs256 requires private_key_pem for signing.
    """
    issued_to = str(issued_to).strip()
    machine = str(machine).strip()
    alg = str(alg or "hs256").lower()
    # basic field checks
    if not issued_to:
        raise ValueError("issued_to required")
    if not expires:
        raise ValueError("expires required (YYYY-MM-DD)")
    # validate date
    try:
        datetime.strptime(expires, "%Y-%m-%d")
    except Exception:
        raise ValueError("invalid expires format, expected YYYY-MM-DD")

    payload = f"{issued_to}|{expires}|{machine}".encode("utf-8")
    if alg == "rs256":
        if not private_key_pem:
            raise ValueError("private key PEM required for rs256")
        signature = _sign_rs256(payload, private_key_pem)
    else:
        raw = payload + ("|" + _SALT).encode("utf-8")
        signature = hashlib.sha256(raw).hexdigest()
        alg = "hs256"
    return {
        "issued_to": issued_to,
        "expires": expires,
        "machine": machine,
        "alg": alg,
        "signature": signature,
    }
