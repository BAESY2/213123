"""Order execution with the dry-run / live safety switch.

In dry-run (default) it logs the intended order and simulates a fill at the
given price. Only when ENABLE_LIVE=true does it route to the real CLOB.

Two live paths:
  * local  — sign + post directly with the in-process key (single machine).
  * remote — POST the order intent to a server-side signer backend
             (REMOTE_SIGNER_URL) that holds the key. Use this when the bot /
             .exe is distributed, so the secret never leaves your server.
"""
from __future__ import annotations

from dataclasses import dataclass

import requests

from .config import settings
from .logger import get_logger
from .polymarket import ClobBroker

log = get_logger("executor")


@dataclass
class Fill:
    token_id: str
    side_label: str       # "UP" / "DOWN"
    price: float
    shares: float
    usdc: float
    live: bool
    ok: bool
    raw: object = None


class Executor:
    def __init__(self, broker: ClobBroker | None = None):
        self.live = settings.enable_live
        self.remote_url = settings.remote_signer_url.rstrip("/") if settings.remote_signer_url else ""
        self._broker = broker
        # Only need a local key-holding broker when live AND not delegating.
        if self.live and not self.remote_url and self._broker is None:
            self._broker = ClobBroker()

    def buy(self, token_id: str, side_label: str, price: float, shares: float, usdc: float) -> Fill:
        if not self.live:
            log.info("[DRY-RUN] BUY %s %.2f shares @ %.3f (~$%.2f) token=%s",
                     side_label, shares, price, usdc, token_id[:12])
            return Fill(token_id, side_label, price, shares, usdc, live=False, ok=True)

        if self.remote_url:
            return self._buy_remote(token_id, side_label, price, shares, usdc)
        return self._buy_local(token_id, side_label, price, shares, usdc)

    def _buy_local(self, token_id, side_label, price, shares, usdc) -> Fill:
        log.warning("[LIVE/local] BUY %s %.2f shares @ %.3f (~$%.2f) token=%s",
                    side_label, shares, price, usdc, token_id[:12])
        try:
            resp = self._broker.buy(token_id, price=price, size=shares, fok=True)
            ok = bool(resp) and (resp.get("success", True) if isinstance(resp, dict) else True)
            if not ok:
                log.error("[LIVE] order rejected: %s", resp)
            return Fill(token_id, side_label, price, shares, usdc, live=True, ok=ok, raw=resp)
        except Exception as exc:
            log.error("[LIVE] order error: %s", exc)
            return Fill(token_id, side_label, price, shares, usdc, live=True, ok=False, raw=str(exc))

    def _buy_remote(self, token_id, side_label, price, shares, usdc) -> Fill:
        """Delegate signing to the backend; client holds no key/secret."""
        log.warning("[LIVE/remote] BUY %s %.2f shares @ %.3f (~$%.2f) -> %s",
                    side_label, shares, price, usdc, self.remote_url)
        headers = {}
        if settings.signer_auth_token:
            headers["X-Signer-Token"] = settings.signer_auth_token
        try:
            resp = requests.post(
                f"{self.remote_url}/order",
                json={"token_id": token_id, "price": round(price, 3),
                      "size": round(shares, 2), "fok": True},
                headers=headers, timeout=10,
            )
            body = resp.json() if resp.content else {}
            ok = resp.ok and bool(body.get("ok", resp.ok))
            if not ok:
                log.error("[LIVE/remote] rejected: %s %s", resp.status_code, body)
            return Fill(token_id, side_label, price, shares, usdc, live=True, ok=ok, raw=body)
        except Exception as exc:
            log.error("[LIVE/remote] order error: %s", exc)
            return Fill(token_id, side_label, price, shares, usdc, live=True, ok=False, raw=str(exc))
