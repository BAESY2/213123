"""Order execution with the dry-run / live safety switch.

In dry-run (default) it logs the intended order and simulates a fill at the
given price. Only when ENABLE_LIVE=true does it route to the real CLOB.
"""
from __future__ import annotations

from dataclasses import dataclass

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
        self._broker = broker
        if self.live and self._broker is None:
            self._broker = ClobBroker()

    def buy(self, token_id: str, side_label: str, price: float, shares: float, usdc: float) -> Fill:
        if not self.live:
            log.info("[DRY-RUN] BUY %s %.2f shares @ %.3f (~$%.2f) token=%s",
                     side_label, shares, price, usdc, token_id[:12])
            return Fill(token_id, side_label, price, shares, usdc, live=False, ok=True)

        log.warning("[LIVE] BUY %s %.2f shares @ %.3f (~$%.2f) token=%s",
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
