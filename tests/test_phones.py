"""Phone normalization to E.164 (spec §2; §11 unit: phone normalization)."""
from __future__ import annotations

import pytest

from core.phones import digits_only, normalize


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+15551234567", "+15551234567"),
        ("+44 20 7946 0958", "+442079460958"),
        ("0015551234567", "+15551234567"),    # international 00 prefix
        ("(555) 123-4567", "+15551234567"),   # bare US 10-digit
        ("1 555 123 4567", "+15551234567"),   # US 11-digit with country code
        ("+1 (555) 123-4567", "+15551234567"),
    ],
)
def test_normalize_valid(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "+1", "12345", "555-123", "+123456789012345678", "hello"],
)
def test_normalize_invalid_raises(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize(raw)


def test_bare_national_number_needs_us_region() -> None:
    with pytest.raises(ValueError):
        normalize("5551234567", default_region="GB")


def test_digits_only() -> None:
    assert digits_only("+1 (555) 123-4567") == "15551234567"
    assert digits_only("9-1-1") == "911"
    assert digits_only("") == ""
    assert digits_only(None) == ""  # type: ignore[arg-type]
