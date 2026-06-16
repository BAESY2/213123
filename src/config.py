"""Configuration loaded from environment / .env.

Every tunable lives here so the strategy can be changed without touching code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # python-dotenv optional at import time
    pass


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _i(name: str, default: int) -> int:
    return int(float(os.getenv(name, default)))


def _b(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() == "true"


@dataclass
class Settings:
    # --- execution mode ---
    enable_live: bool = _b("ENABLE_LIVE", False)

    # --- polymarket / clob ---
    private_key: str = os.getenv("POLYMARKET_PRIVATE_KEY", "")
    clob_host: str = os.getenv("CLOB_HOST", "https://clob.polymarket.com")
    chain_id: int = _i("CHAIN_ID", 137)
    signature_type: int = _i("SIGNATURE_TYPE", 0)
    funder_address: str = os.getenv("POLYMARKET_FUNDER_ADDRESS", "")

    # Pre-derived L2 API creds (optional; otherwise derived from the key at runtime).
    api_key: str = os.getenv("POLYMARKET_API_KEY", "")
    api_secret: str = os.getenv("POLYMARKET_API_SECRET", "")
    api_passphrase: str = os.getenv("POLYMARKET_API_PASSPHRASE", "")

    # --- server-side signing (keep key/secret off the client/.exe) ---
    # If set, the bot delegates order signing to this backend instead of
    # holding the private key locally.
    remote_signer_url: str = os.getenv("REMOTE_SIGNER_URL", "")
    # Shared secret between bot and signer backend (X-Signer-Token header).
    signer_auth_token: str = os.getenv("SIGNER_AUTH_TOKEN", "")

    # --- gamma / market discovery ---
    gamma_host: str = os.getenv("GAMMA_HOST", "https://gamma-api.polymarket.com")
    # Slug template for the recurring 5-min BTC market; {ts} = window start unix ts.
    slug_template: str = os.getenv("SLUG_TEMPLATE", "btc-updown-5m-{ts}")
    window_sec: int = _i("WINDOW_SEC", 300)

    # --- price feed ---
    price_feed_url: str = os.getenv(
        "PRICE_FEED_URL",
        "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
    )

    # --- strategy ---
    momentum_lookback_sec: int = _i("MOMENTUM_LOOKBACK_SEC", 60)
    momentum_scale: float = _f("MOMENTUM_SCALE", 0.0008)
    momentum_weight: float = _f("MOMENTUM_WEIGHT", 0.6)
    min_edge: float = _f("MIN_EDGE", 0.05)
    min_confidence: float = _f("MIN_CONFIDENCE", 0.15)
    decision_window_sec: int = _i("DECISION_WINDOW_SEC", 90)

    # --- risk ---
    stake_usdc: float = _f("STAKE_USDC", 5)
    max_open_usdc: float = _f("MAX_OPEN_USDC", 20)
    max_trades_per_day: int = _i("MAX_TRADES_PER_DAY", 50)
    max_price: float = _f("MAX_PRICE", 0.95)
    min_price: float = _f("MIN_PRICE", 0.05)

    # --- aggressive / compounding mode (the "$40 -> $1k -> $10k" plan) ---
    # When true, stake is a fraction of the *current* bankroll instead of a fixed
    # STAKE_USDC, so winnings compound. This is high variance by design.
    compounding: bool = _b("COMPOUNDING", False)
    # Fraction of bankroll to stake per trade in compounding mode (0..1).
    bankroll_fraction: float = _f("BANKROLL_FRACTION", 0.5)
    # Starting bankroll for sizing/targets (USDC).
    start_bankroll: float = _f("START_BANKROLL", 40)
    # Stop trading (take profit) once bankroll reaches this. 0 = disabled.
    bankroll_target: float = _f("BANKROLL_TARGET", 1000)
    # Stop trading (stop loss) once bankroll falls to this. 0 = disabled.
    bankroll_floor: float = _f("BANKROLL_FLOOR", 0)
    # Hard wall-clock stop (minutes) for the whole session. 0 = disabled.
    session_minutes: int = _i("SESSION_MINUTES", 180)

    # --- loop ---
    poll_interval_sec: int = _i("POLL_INTERVAL_SEC", 5)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
