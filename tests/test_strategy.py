"""Unit tests for the strategy and risk math (run with: pytest)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.strategy import compute_signal, should_trade  # noqa: E402
from src.price_feed import PriceFeed  # noqa: E402


def test_momentum_up_pushes_prob_up():
    sig = compute_signal(momentum_return=0.002, book_imbalance=None, market_prob_up=0.5)
    assert sig.side == "UP"
    assert sig.prob_up > 0.5


def test_momentum_down_pushes_prob_down():
    sig = compute_signal(momentum_return=-0.002, book_imbalance=None, market_prob_up=0.5)
    assert sig.side == "DOWN"
    assert sig.prob_up < 0.5


def test_no_inputs_is_neutral_and_no_trade():
    sig = compute_signal(None, None, None)
    assert sig.side is None
    assert not should_trade(sig)


def test_imbalance_only_signal():
    sig = compute_signal(momentum_return=None, book_imbalance=0.8, market_prob_up=0.5)
    assert sig.side == "UP"
    assert sig.confidence > 0


def test_edge_gate_blocks_overpriced_market():
    # Model mildly likes UP but market already prices UP at 0.99 -> negative edge.
    sig = compute_signal(momentum_return=0.0005, book_imbalance=None, market_prob_up=0.99)
    assert sig.edge < 0
    assert not should_trade(sig)


def test_price_feed_momentum():
    feed = PriceFeed(lookback_sec=60)
    feed.add_point(100.0, ts=0)
    feed.add_point(101.0, ts=30)
    r = feed.momentum_return()
    assert r is not None and r > 0
