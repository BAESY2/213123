"""Polymarket L2 (API-key/HMAC) request signing — server-side.

Implements the scheme documented at
docs.polymarket.com/api-reference/authentication (and mirrored in the official
py-clob-client `signing/hmac.py`):

    message    = str(timestamp) + method + requestPath + body?
    body        : single quotes normalised to double quotes (cross-lang parity)
    key         = urlsafe_b64decode(api_secret)
    signature   = urlsafe_b64encode( HMAC_SHA256(key, message) )

L2 headers attached to authenticated CLOB requests:
    POLY_ADDRESS, POLY_SIGNATURE, POLY_TIMESTAMP, POLY_API_KEY, POLY_PASSPHRASE

SECURITY: the api_secret must live ONLY on the server/backend. Never ship it in
client-side code or a distributed .exe. See `signer_server.py`.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass


@dataclass
class ApiCreds:
    api_key: str
    secret: str       # base64-url encoded secret from create_or_derive_api_creds
    passphrase: str


def build_hmac_signature(
    secret: str,
    timestamp: str | int,
    method: str,
    request_path: str,
    body: str | None = None,
) -> str:
    """Return the urlsafe-base64 HMAC-SHA256 signature for an L2 request."""
    message = f"{timestamp}{method}{request_path}"
    if body is not None:
        # Match py-clob-client / TS / Go: normalise single quotes to double.
        message += str(body).replace("'", '"')

    key = base64.urlsafe_b64decode(secret)
    digest = hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8")


def build_l2_headers(
    creds: ApiCreds,
    address: str,
    method: str,
    request_path: str,
    body: str | None = None,
    timestamp: int | None = None,
) -> dict[str, str]:
    """Build the five POLY_* headers for an authenticated CLOB request."""
    ts = str(timestamp if timestamp is not None else int(time.time()))
    sig = build_hmac_signature(creds.secret, ts, method.upper(), request_path, body)
    return {
        "POLY_ADDRESS": address,
        "POLY_SIGNATURE": sig,
        "POLY_TIMESTAMP": ts,
        "POLY_API_KEY": creds.api_key,
        "POLY_PASSPHRASE": creds.passphrase,
    }
