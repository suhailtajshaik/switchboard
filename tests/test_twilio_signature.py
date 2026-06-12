"""Twilio webhook signature validation (S2; §11 unit: valid, forged,
replayed). HMAC-SHA1 over the exact public URL + sorted POST params."""
from __future__ import annotations

import pytest

from adapters.twilio_signature import compute_signature, validate

AUTH = "12345"
URL = "https://mycompany.com/myapp.php?foo=1&bar=2"
PARAMS = {
    "CallSid": "CA1234567890ABCDE",
    "Caller": "+14158675310",
    "Digits": "1234",
    "From": "+14158675310",
    "To": "+18005551212",
}


def test_valid_signature_accepted() -> None:
    sig = compute_signature(AUTH, URL, PARAMS)
    assert validate(AUTH, URL, PARAMS, sig)


def test_known_vector_regression() -> None:
    # Pinned output for this url/params/token combination, verified equal to
    # twilio.request_validator.RequestValidator.compute_signature.
    assert compute_signature(AUTH, URL, PARAMS) == "GvWf1cFY/Q7PnoempGyD5oXAezc="


def test_matches_official_twilio_sdk() -> None:
    # Cross-check against the vendor implementation when the runtime deps
    # are installed (skipped in dev-only CI, which installs requirements-dev).
    twilio_validator = pytest.importorskip("twilio.request_validator")
    official = twilio_validator.RequestValidator(AUTH).compute_signature(URL, PARAMS)
    assert compute_signature(AUTH, URL, PARAMS) == official


def test_missing_signature_rejected() -> None:
    assert not validate(AUTH, URL, PARAMS, None)
    assert not validate(AUTH, URL, PARAMS, "")


def test_forged_signature_rejected() -> None:
    assert not validate(AUTH, URL, PARAMS, "AAAAAAAAAAAAAAAAAAAAAAAAAAA=")


def test_tampered_params_rejected() -> None:
    sig = compute_signature(AUTH, URL, PARAMS)
    tampered = dict(PARAMS, To="+19998887777")
    assert not validate(AUTH, URL, tampered, sig)


def test_replay_to_different_url_rejected() -> None:
    sig = compute_signature(AUTH, URL, PARAMS)
    assert not validate(AUTH, "https://evil.example.com/twilio/voice", PARAMS, sig)
    # Same host, different scheme/path also fails — validation is over the
    # exact public URL (the classic 403-behind-proxy gotcha).
    assert not validate(AUTH, URL + "&x=1", PARAMS, sig)


def test_wrong_auth_token_rejected() -> None:
    sig = compute_signature(AUTH, URL, PARAMS)
    assert not validate("other-token", URL, PARAMS, sig)


def test_param_insertion_order_irrelevant() -> None:
    reordered = dict(reversed(list(PARAMS.items())))
    assert compute_signature(AUTH, URL, reordered) == compute_signature(AUTH, URL, PARAMS)
