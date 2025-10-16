# backend/app/core/privacy.py
from __future__ import annotations
import re
from typing import Any, Dict

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(\+?\d[\d\s\-]{7,}\d)")

SENSITIVE_KEYS = {"email", "phone", "tel", "mobile", "address"}

REDACT = "[REDACTED]"

def _redact_string(s: str) -> str:
    s = EMAIL_RE.sub(REDACT, s)
    s = PHONE_RE.sub(REDACT, s)
    return s

def _redact_value(v: Any) -> Any:
    if isinstance(v, str):
        return _redact_string(v)
    if isinstance(v, list):
        return [_redact_value(x) for x in v]
    if isinstance(v, dict):
        return _redact_dict(v)
    return v

def _redact_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in d.items():
        kl = k.lower()
        if kl in SENSITIVE_KEYS:
            out[k] = REDACT
        else:
            out[k] = _redact_value(v)
    return out

def redact_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Redact emails/phones/addresses in any nested structure."""
    if not isinstance(payload, dict):
        return payload
    return _redact_dict(payload)
