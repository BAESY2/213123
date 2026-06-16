"""Server-side signing backend (keeps secrets OFF the client / out of the .exe).

Why this exists: the Polymarket docs are explicit —
"Never expose your API secret in client-side code. All authenticated requests
should originate from your backend." If you embed the private key / API secret
in a distributed .exe, anyone can extract it and drain the wallet.

This tiny Flask service holds the L1 private key, derives L2 API creds on
startup, and exposes a minimal authenticated endpoint that creates + posts a
signed order to the CLOB. The trading bot (client) calls it via
REMOTE_SIGNER_URL and never sees the key/secret.

Run:
    pip install flask
    SIGNER_AUTH_TOKEN=<shared-secret> POLYMARKET_PRIVATE_KEY=0x... \
        python -m src.signer_server
"""
from __future__ import annotations

import os

from .config import settings
from .logger import get_logger

log = get_logger("signer")


def create_app():
    from flask import Flask, jsonify, request

    from .polymarket import ClobBroker

    app = Flask(__name__)
    broker = ClobBroker()
    auth_token = os.getenv("SIGNER_AUTH_TOKEN", "")

    def _authorized(req) -> bool:
        # Shared-secret gate so only your bot can ask the server to sign orders.
        if not auth_token:
            return True  # no token configured (dev only)
        return req.headers.get("X-Signer-Token", "") == auth_token

    @app.get("/health")
    def health():
        return jsonify(status="ok", live=settings.enable_live)

    @app.get("/book/<token_id>")
    def book(token_id: str):
        if not _authorized(request):
            return jsonify(error="unauthorized"), 401
        bid, ask = broker.best_prices(token_id)
        imb = broker.book_imbalance(token_id)
        return jsonify(best_bid=bid, best_ask=ask, imbalance=imb)

    @app.post("/order")
    def order():
        if not _authorized(request):
            return jsonify(error="unauthorized"), 401
        data = request.get_json(force=True) or {}
        try:
            token_id = str(data["token_id"])
            price = float(data["price"])
            size = float(data["size"])
            fok = bool(data.get("fok", True))
        except (KeyError, ValueError, TypeError) as exc:
            return jsonify(error=f"bad request: {exc}"), 400

        if not settings.enable_live:
            # Backend also respects the master safety switch.
            log.info("[SIGNER DRY-RUN] would BUY %s %.2f@%.3f", token_id[:12], size, price)
            return jsonify(ok=True, dry_run=True)

        try:
            resp = broker.buy(token_id, price=price, size=size, fok=fok)
            return jsonify(ok=True, result=resp)
        except Exception as exc:
            log.error("signer order failed: %s", exc)
            return jsonify(ok=False, error=str(exc)), 502

    return app


def main() -> None:
    host = os.getenv("SIGNER_HOST", "127.0.0.1")
    port = int(os.getenv("SIGNER_PORT", "8787"))
    if not os.getenv("SIGNER_AUTH_TOKEN"):
        log.warning("SIGNER_AUTH_TOKEN not set — endpoint is UNAUTHENTICATED (dev only).")
    log.warning("starting signer backend on %s:%d (secrets stay here, not on the client)", host, port)
    create_app().run(host=host, port=port)


if __name__ == "__main__":
    main()
