"""Twilio webhook signature validation (S2) — stdlib implementation of the
documented scheme: HMAC-SHA1 over the exact public URL + alphabetically
sorted POST params, Base64-encoded, compared constant-time against the
X-Twilio-Signature header.
Reference: https://www.twilio.com/docs/usage/security#validating-requests
"""
from __future__ import annotations

import base64
import hashlib
import hmac


def compute_signature(auth_token: str, url: str, params: dict[str, str]) -> str:
    payload = url + "".join(k + params[k] for k in sorted(params))
    digest = hmac.new(auth_token.encode(), payload.encode("utf-8"),
                      hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def validate(auth_token: str, url: str, params: dict[str, str],
             signature_header: str | None) -> bool:
    """Reject (False) on missing/forged signatures *before* any business
    parsing — the gateway returns 403 when this is False."""
    if not signature_header:
        return False
    expected = compute_signature(auth_token, url, params)
    return hmac.compare_digest(expected, signature_header)
