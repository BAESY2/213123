"""Main trading loop for the Polymarket BTC 5-minute up/down bot.

Per 5-minute window:
  1. Continuously poll the BTC price feed (builds momentum history).
  2. Capture the window's opening reference price.
  3. Inside the final DECISION_WINDOW_SEC, compute the combined signal
     (momentum + order-book imbalance) and, if it clears the gates, buy the
     UP or DOWN token once.
  4. After the window closes, settle the position and update the bankroll.

Dry-run settles against the local price feed (close vs open). Live orders are
routed to the CLOB and resolved on-chain by Polymarket; the bankroll shown in
live mode is an estimate for monitoring.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from .config import settings
from .executor import Executor, Fill
from .logger import get_logger
from .polymarket import ClobBroker, Market, discover_market
from .price_feed import PriceFeed
from .risk import RiskManager
from .strategy import compute_signal, should_trade

log = get_logger("bot")


@dataclass
class OpenPosition:
    market: Market
    fill: Fill
    open_ref_price: float


class TradingBot:
    def __init__(self):
        self.feed = PriceFeed()
        self.risk = RiskManager()
        self.broker = ClobBroker() if settings.enable_live else None
        self.executor = Executor(self.broker)
        self.position: OpenPosition | None = None
        self._traded_windows: set[int] = set()
        self._open_ref: dict[int, float] = {}

    # ------------------------------------------------------------------ #
    def _market_prob_up(self, market: Market) -> float | None:
        """Best estimate of P(Up) the market is charging right now."""
        if self.broker is not None:
            bid, ask = self.broker.best_prices(market.up_token_id)
            if bid is not None and ask is not None:
                return (bid + ask) / 2
        return market.up_price

    def _imbalance(self, market: Market) -> float | None:
        if self.broker is not None:
            return self.broker.book_imbalance(market.up_token_id)
        return None

    # ------------------------------------------------------------------ #
    def _maybe_trade(self, market: Market) -> None:
        if self.position is not None or market.window_start in self._traded_windows:
            return
        if market.seconds_left > settings.decision_window_sec:
            return  # too early; wait for sharper signal near the close
        if not self.risk.can_trade():
            return

        momentum = self.feed.momentum_return()
        imbalance = self._imbalance(market)
        market_prob_up = self._market_prob_up(market)

        sig = compute_signal(momentum, imbalance, market_prob_up)
        log.info("signal | %s", sig.reason)
        if not should_trade(sig):
            return

        token_id = market.up_token_id if sig.side == "UP" else market.down_token_id
        # Price we're willing to pay: market side price, capped by risk band.
        side_price = market_prob_up if sig.side == "UP" else (
            (1 - market_prob_up) if market_prob_up is not None else 0.5)
        side_price = side_price if side_price is not None else 0.5
        side_price = min(settings.max_price, max(settings.min_price, side_price))

        usdc, shares = self.risk.stake_for(side_price)
        if usdc <= 0 or shares <= 0:
            log.info("sizing produced 0 stake; skipping")
            return

        fill = self.executor.buy(token_id, sig.side, side_price, shares, usdc)
        if not fill.ok:
            log.warning("order not filled; not opening position")
            return

        self.risk.on_open(usdc)
        self._traded_windows.add(market.window_start)
        self.position = OpenPosition(
            market=market,
            fill=fill,
            open_ref_price=self._open_ref.get(market.window_start, self.feed.last or 0.0),
        )

    # ------------------------------------------------------------------ #
    def _maybe_settle(self) -> None:
        if self.position is None:
            return
        pos = self.position
        if time.time() < pos.market.window_end:
            return

        close_price = self.feed.last or pos.open_ref_price
        went_up = close_price >= pos.open_ref_price
        won = (pos.fill.side_label == "UP" and went_up) or (
            pos.fill.side_label == "DOWN" and not went_up)
        payout = pos.fill.shares * 1.0 if won else 0.0

        log.info("RESOLVE window=%s side=%s open=%.2f close=%.2f -> %s",
                 pos.market.window_start, pos.fill.side_label,
                 pos.open_ref_price, close_price, "WIN" if won else "LOSS")
        self.risk.on_settle(pos.fill.usdc, payout)
        self.position = None

    # ------------------------------------------------------------------ #
    def step(self) -> None:
        price = self.feed.poll()
        market = discover_market()
        if market is not None:
            # Capture opening reference once per window.
            if market.window_start not in self._open_ref and price is not None:
                self._open_ref[market.window_start] = price
            self._maybe_trade(market)
        self._maybe_settle()

    def run(self) -> None:
        mode = "LIVE  *** REAL FUNDS ***" if settings.enable_live else "DRY-RUN (no real orders)"
        log.warning("=" * 64)
        log.warning("BTC 5-min bot starting | mode=%s", mode)
        log.warning("bankroll=$%.2f compounding=%s frac=%.2f target=$%.0f session=%dm",
                    self.risk.state.bankroll, settings.compounding,
                    settings.bankroll_fraction, settings.bankroll_target,
                    settings.session_minutes)
        log.warning("=" * 64)

        try:
            while True:
                stop = self.risk.stop_reason()
                if stop and self.position is None:
                    log.warning("STOP: %s | final bankroll=$%.2f", stop, self.risk.state.bankroll)
                    break
                try:
                    self.step()
                except Exception as exc:  # never let one bad tick kill the session
                    log.error("step error: %s", exc)
                time.sleep(settings.poll_interval_sec)
        except KeyboardInterrupt:
            log.warning("interrupted | bankroll=$%.2f", self.risk.state.bankroll)
