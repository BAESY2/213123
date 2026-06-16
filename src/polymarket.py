"""Polymarket integration: 5-min BTC market discovery + CLOB order routing.

Market discovery uses the deterministic slug pattern documented by community
tools (e.g. handiko/Polymarket-Market-Finder, Archetapp's 5-min bot gist):

    window_ts = now - (now % 300)        # start of current 5-min window
    slug      = f"btc-updown-5m-{window_ts}"
    GET {gamma}/events?slug=<slug>       -> markets[].clobTokenIds (Up/Down)

Order routing uses the official py-clob-client. It is imported lazily so the
bot can run in dry-run / backtest mode without the dependency installed.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import requests

from .config import settings
from .logger import get_logger

log = get_logger("polymarket")


@dataclass
class Market:
    slug: str
    window_start: int
    window_end: int
    up_token_id: str
    down_token_id: str
    up_price: float | None = None  # market-implied P(up), 0..1
    down_price: float | None = None

    @property
    def seconds_left(self) -> float:
        return max(0.0, self.window_end - time.time())


def current_window_start(now: float | None = None, window_sec: int | None = None) -> int:
    now = time.time() if now is None else now
    w = window_sec or settings.window_sec
    return int(now - (now % w))


def discover_market(now: float | None = None) -> Market | None:
    """Find the active 5-min BTC up/down market via Gamma API."""
    ws = current_window_start(now)
    slug = settings.slug_template.format(ts=ws)
    url = f"{settings.gamma_host}/events"
    try:
        resp = requests.get(url, params={"slug": slug}, timeout=5)
        resp.raise_for_status()
        events = resp.json()
    except Exception as exc:
        log.warning("gamma discovery failed for %s: %s", slug, exc)
        return None

    if not events:
        log.debug("no event for slug %s yet", slug)
        return None

    event = events[0]
    markets = event.get("markets") or []
    if not markets:
        return None
    m = markets[0]

    token_ids = m.get("clobTokenIds")
    if isinstance(token_ids, str):
        import json

        try:
            token_ids = json.loads(token_ids)
        except Exception:
            token_ids = []
    if not token_ids or len(token_ids) < 2:
        log.warning("market %s missing clobTokenIds", slug)
        return None

    # Outcomes order is typically ["Up"/"Yes", "Down"/"No"].
    up_id, down_id = str(token_ids[0]), str(token_ids[1])

    up_price = down_price = None
    prices = m.get("outcomePrices")
    if isinstance(prices, str):
        import json

        try:
            prices = json.loads(prices)
        except Exception:
            prices = None
    if prices and len(prices) >= 2:
        try:
            up_price, down_price = float(prices[0]), float(prices[1])
        except Exception:
            pass

    return Market(
        slug=slug,
        window_start=ws,
        window_end=ws + settings.window_sec,
        up_token_id=up_id,
        down_token_id=down_id,
        up_price=up_price,
        down_price=down_price,
    )


class ClobBroker:
    """Thin wrapper over py-clob-client. Lazily initialised."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _build_client(self):
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import ApiCreds

        if not settings.private_key:
            raise RuntimeError("POLYMARKET_PRIVATE_KEY required for live trading")

        kwargs = dict(
            host=settings.clob_host,
            key=settings.private_key,
            chain_id=settings.chain_id,
        )
        if settings.signature_type:
            kwargs["signature_type"] = settings.signature_type
            if settings.funder_address:
                kwargs["funder"] = settings.funder_address

        client = ClobClient(**kwargs)
        # Use pre-derived L2 creds if supplied (api_key/secret/passphrase),
        # else derive them from the private key (L1 -> L2).
        if settings.api_key and settings.api_secret and settings.api_passphrase:
            creds = ApiCreds(
                api_key=settings.api_key,
                api_secret=settings.api_secret,
                api_passphrase=settings.api_passphrase,
            )
        else:
            creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        log.info("CLOB client ready (host=%s)", settings.clob_host)
        return client

    def best_prices(self, token_id: str) -> tuple[float | None, float | None]:
        """Return (best_bid, best_ask) for a token from the CLOB order book."""
        try:
            book = self.client.get_order_book(token_id)
            best_bid = float(book.bids[0].price) if book.bids else None
            best_ask = float(book.asks[0].price) if book.asks else None
            return best_bid, best_ask
        except Exception as exc:
            log.warning("order book fetch failed: %s", exc)
            return None, None

    def book_imbalance(self, token_id: str, depth: int = 5) -> float | None:
        """(bid_size - ask_size) / (bid_size + ask_size) over top `depth` levels.

        Range [-1, 1]; positive => buy pressure on this token.
        """
        try:
            book = self.client.get_order_book(token_id)
            bid_sz = sum(float(l.size) for l in (book.bids or [])[:depth])
            ask_sz = sum(float(l.size) for l in (book.asks or [])[:depth])
            total = bid_sz + ask_sz
            if total == 0:
                return None
            return (bid_sz - ask_sz) / total
        except Exception as exc:
            log.warning("imbalance fetch failed: %s", exc)
            return None

    def buy(self, token_id: str, price: float, size: float, fok: bool = True):
        """Place a BUY order. size = number of shares. Returns API response."""
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY

        args = OrderArgs(token_id=token_id, price=round(price, 3), size=round(size, 2), side=BUY)
        order_type = OrderType.FOK if fok else OrderType.GTC
        signed = self.client.create_order(args)
        return self.client.post_order(signed, order_type)
