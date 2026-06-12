"""Phone-number normalization to E.164 (spec §2).

Deliberately dependency-free. For exotic international formats, swap in the
`phonenumbers` package behind this same function.
"""
from __future__ import annotations

import re

_CLEAN = re.compile(r"[\s\-().]")


def normalize(raw: str, default_region: str = "US") -> str:
    """Return E.164 (+<8-15 digits>) or raise ValueError."""
    if not raw:
        raise ValueError("empty phone number")
    s = _CLEAN.sub("", raw.strip())
    if s.startswith("00"):
        s = "+" + s[2:]
    if s.startswith("+"):
        digits = s[1:]
        if digits.isdigit() and 8 <= len(digits) <= 15:
            return "+" + digits
        raise ValueError(f"not a valid E.164 number: {raw!r}")
    if s.isdigit() and default_region == "US":
        if len(s) == 10:
            return "+1" + s
        if len(s) == 11 and s.startswith("1"):
            return "+" + s
    raise ValueError(f"cannot normalize {raw!r} (region {default_region})")


def digits_only(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")
