"""Entry point: `python -m src.main` or the packaged executable."""
from __future__ import annotations

from .bot import TradingBot
from .config import settings
from .logger import get_logger

log = get_logger("main")


def main() -> None:
    if settings.enable_live:
        log.warning("ENABLE_LIVE=true -> REAL orders will be placed with REAL USDC.")
    bot = TradingBot()
    bot.run()


if __name__ == "__main__":
    main()
