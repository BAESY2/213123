"""External BTC spot price feed + rolling momentum signal.

Used to estimate short-term directional pressure for the 5-min window.
Default source is Binance public ticker (no API key required).
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

import requests

from .config import settings
from .logger import get_logger

log = get_logger("price_feed")


@dataclass
class PricePoint:
    ts: float
    price: float


class PriceFeed:
    def __init__(self, url: str | None = None, lookback_sec: int | None = None):
        self.url = url or settings.price_feed_url
        self.lookback_sec = lookback_sec or settings.momentum_lookback_sec
        self._points: deque[PricePoint] = deque(maxlen=2000)

    def poll(self) -> float | None:
        """Fetch the latest spot price and store it. Returns price or None."""
        try:
            resp = requests.get(self.url, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            price = float(data["price"]) if "price" in data else float(data)
        except Exception as exc:  # network / parse errors shouldn't kill the loop
            log.warning("price poll failed: %s", exc)
            return None
        self._points.append(PricePoint(time.time(), price))
        return price

    def add_point(self, price: float, ts: float | None = None) -> None:
        """Manually feed a price (used by tests / backtests)."""
        self._points.append(PricePoint(ts if ts is not None else time.time(), price))

    @property
    def last(self) -> float | None:
        return self._points[-1].price if self._points else None

    def momentum_return(self) -> float | None:
        """Return = (last - price_lookback_ago) / price_lookback_ago.

        Positive => upward pressure. None if not enough history.
        """
        if len(self._points) < 2:
            return None
        now = self._points[-1].ts
        cutoff = now - self.lookback_sec
        ref = None
        for pt in self._points:
            if pt.ts >= cutoff:
                ref = pt
                break
        if ref is None or ref.price == 0:
            return None
        return (self._points[-1].price - ref.price) / ref.price
