from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple


LICENSE_PATH = Path.home() / ".mcp/license.json"
# 说明：SALT 仅为占位示例，生产建议改为非对称签名验证
_SALT = os.environ.get("MCP_LICENSE_SALT", "mcp-demo-salt-202409")


def _read_license(path: Path = LICENSE_PATH) -> Tuple[Dict[str, Any], bool]:
    if not path.exists():
        return {}, False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}, True
    except Exception:
        return {}, False


def verify_license(path: Path = LICENSE_PATH) -> Dict[str, Any]:
    data, exists = _read_license(path)
    if not exists:
        return {"ok": False, "activated": False, "reason": "license file missing"}
    issued_to = str(data.get("issued_to", "")).strip()
    expires = str(data.get("expires", "")).strip()  # yyyy-mm-dd
    machine = str(data.get("machine", "")).strip()
    signature = str(data.get("signature", "")).strip()
    now = datetime.utcnow().date()
    valid_date = True
    if expires:
        try:
            valid_date = now <= datetime.strptime(expires, "%Y-%m-%d").date()
        except Exception:
            valid_date = False
    # 计算占位签名（演示用）
    raw = f"{issued_to}|{expires}|{machine}|{_SALT}".encode("utf-8")
    calc = hashlib.sha256(raw).hexdigest()
    sig_ok = bool(signature and signature.lower() == calc)
    return {
        "ok": bool(sig_ok and valid_date),
        "activated": True,
        "issued_to": issued_to,
        "expires": expires,
        "machine": machine,
        "signature_ok": sig_ok,
        "date_ok": valid_date,
    }

