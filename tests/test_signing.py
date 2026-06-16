"""Tests for L2 HMAC request signing (must match py-clob-client/TS/Go)."""
import base64
import hashlib
import hmac
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.signing import ApiCreds, build_hmac_signature, build_l2_headers  # noqa: E402


def _reference(secret, ts, method, path, body=None):
    msg = f"{ts}{method}{path}"
    if body is not None:
        msg += str(body).replace("'", '"')
    key = base64.urlsafe_b64decode(secret)
    return base64.urlsafe_b64encode(
        hmac.new(key, msg.encode(), hashlib.sha256).digest()
    ).decode()


def test_signature_matches_reference_no_body():
    secret = base64.urlsafe_b64encode(b"super-secret-key-bytes").decode()
    sig = build_hmac_signature(secret, 1700000000, "GET", "/order")
    assert sig == _reference(secret, 1700000000, "GET", "/order")


def test_signature_normalises_quotes_in_body():
    secret = base64.urlsafe_b64encode(b"k").decode()
    body = "{'price': 0.5}"  # single quotes -> normalised to double
    sig = build_hmac_signature(secret, 1, "POST", "/order", body)
    assert sig == _reference(secret, 1, "POST", "/order", body)


def test_l2_headers_complete():
    secret = base64.urlsafe_b64encode(b"k").decode()
    creds = ApiCreds(api_key="abc", secret=secret, passphrase="pp")
    h = build_l2_headers(creds, "0xADDR", "POST", "/order", body="{}", timestamp=42)
    assert h["POLY_API_KEY"] == "abc"
    assert h["POLY_ADDRESS"] == "0xADDR"
    assert h["POLY_PASSPHRASE"] == "pp"
    assert h["POLY_TIMESTAMP"] == "42"
    assert h["POLY_SIGNATURE"] == _reference(secret, 42, "POST", "/order", "{}")
