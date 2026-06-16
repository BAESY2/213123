"""Risk management & position sizing, including the aggressive compounding mode.

Tracks a bankroll, enforces daily trade caps / open-exposure caps, and decides
how much USDC to stake per trade. Honest note: the "$40 -> $1k -> $10k" plan is
implemented as *fractional compounding*, which is high variance by design.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .config import settings
from .logger import get_logger

log = get_logger("risk")


@dataclass
class RiskState:
    bankroll: float = field(default_factory=lambda: settings.start_bankroll)
    open_usdc: float = 0.0
    trades_today: int = 0
    _day: int = field(default_factory=lambda: int(time.time() // 86400))
    started_at: float = field(default_factory=time.time)

    def _roll_day(self) -> None:
        today = int(time.time() // 86400)
        if today != self._day:
            self._day = today
            self.trades_today = 0


class RiskManager:
    def __init__(self, state: RiskState | None = None):
        self.state = state or RiskState()

    # --- stop conditions -------------------------------------------------
    def session_expired(self) -> bool:
        if settings.session_minutes <= 0:
            return False
        return (time.time() - self.state.started_at) >= settings.session_minutes * 60

    def target_hit(self) -> bool:
        return settings.bankroll_target > 0 and self.state.bankroll >= settings.bankroll_target

    def floor_hit(self) -> bool:
        floor = settings.bankroll_floor
        # Always stop if we can't afford the minimum ticket.
        return self.state.bankroll < max(floor, 1.0)

    def stop_reason(self) -> str | None:
        if self.target_hit():
            return f"target reached: bankroll ${self.state.bankroll:.2f} >= ${settings.bankroll_target:.0f}"
        if self.floor_hit():
            return f"floor reached: bankroll ${self.state.bankroll:.2f}"
        if self.session_expired():
            return f"session time limit ({settings.session_minutes}m) reached"
        return None

    # --- sizing ----------------------------------------------------------
    def can_trade(self) -> bool:
        self.state._roll_day()
        if self.stop_reason():
            return False
        if self.state.trades_today >= settings.max_trades_per_day:
            return False
        if self.state.open_usdc >= settings.max_open_usdc:
            return False
        return True

    def stake_for(self, price: float) -> tuple[float, float]:
        """Return (usdc_to_spend, shares) for a buy at `price`.

        Compounding mode: spend `bankroll_fraction` of current bankroll.
        Flat mode: spend fixed STAKE_USDC.
        """
        if settings.compounding:
            usdc = self.state.bankroll * settings.bankroll_fraction
        else:
            usdc = settings.stake_usdc

        # Respect remaining open-exposure room and available bankroll.
        usdc = min(usdc, settings.max_open_usdc - self.state.open_usdc, self.state.bankroll)
        usdc = max(0.0, usdc)
        shares = (usdc / price) if price > 0 else 0.0
        return round(usdc, 2), round(shares, 2)

    # --- bookkeeping -----------------------------------------------------
    def on_open(self, usdc: float) -> None:
        self.state._roll_day()
        self.state.open_usdc += usdc
        self.state.trades_today += 1
        self.state.bankroll -= usdc
        log.info("OPEN  -%.2f USDC | bankroll=%.2f open=%.2f trades=%d",
                 usdc, self.state.bankroll, self.state.open_usdc, self.state.trades_today)

    def on_settle(self, staked_usdc: float, payout_usdc: float) -> None:
        """payout_usdc = shares * 1.0 if won, else 0 (Polymarket resolves to $1/$0)."""
        self.state.open_usdc = max(0.0, self.state.open_usdc - staked_usdc)
        self.state.bankroll += payout_usdc
        pnl = payout_usdc - staked_usdc
        log.info("SETTLE %+.2f USDC | bankroll=%.2f open=%.2f",
                 pnl, self.state.bankroll, self.state.open_usdc)
