"""Combined prediction strategy: price momentum + order-book imbalance.

Outputs a `Signal` containing:
  - prob_up:   model estimate of P(Up wins) in [0, 1]
  - side:      "UP" / "DOWN" / None
  - confidence:|prob_up - 0.5| * 2  in [0, 1]
  - edge:      how much better the model thinks the side is vs market price

Pluggable: tweak weights/scales via config, or swap the math here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .config import settings


@dataclass
class Signal:
    prob_up: float
    side: str | None
    confidence: float
    edge: float
    momentum: float | None
    imbalance: float | None
    market_prob_up: float | None
    reason: str = ""


def _tanh_signal(value: float, scale: float) -> float:
    """Map an unbounded value to [-1, 1] via tanh."""
    if scale <= 0:
        return 0.0
    return math.tanh(value / scale)


def compute_signal(
    momentum_return: float | None,
    book_imbalance: float | None,
    market_prob_up: float | None,
) -> Signal:
    """Blend signals into a directional probability and trade decision.

    momentum_return: short-term BTC % return (e.g. 0.0005 = +0.05%).
    book_imbalance:  imbalance of the UP token book in [-1, 1].
    market_prob_up:  current market price of UP token in [0, 1] (the "fair" line).
    """
    w = settings.momentum_weight  # momentum weight; (1-w) => imbalance weight

    components: list[tuple[float, float]] = []  # (value in [-1,1], weight)
    if momentum_return is not None:
        components.append((_tanh_signal(momentum_return, settings.momentum_scale), w))
    if book_imbalance is not None:
        components.append((max(-1.0, min(1.0, book_imbalance)), 1.0 - w))

    if not components:
        return Signal(0.5, None, 0.0, 0.0, momentum_return, book_imbalance,
                      market_prob_up, reason="no signal inputs")

    wsum = sum(weight for _, weight in components)
    blended = sum(val * weight for val, weight in components) / wsum  # [-1, 1]

    # Map directional score [-1,1] -> probability [0,1].
    prob_up = 0.5 + 0.5 * blended
    prob_up = min(0.999, max(0.001, prob_up))
    confidence = abs(blended)

    side = "UP" if prob_up > 0.5 else "DOWN"
    model_side_prob = prob_up if side == "UP" else 1.0 - prob_up

    # Edge = model probability of chosen side minus what the market charges for it.
    edge = 0.0
    if market_prob_up is not None:
        market_side_prob = market_prob_up if side == "UP" else 1.0 - market_prob_up
        edge = model_side_prob - market_side_prob
    else:
        # No market line available: edge proxied by confidence over the coin-flip.
        edge = model_side_prob - 0.5

    reason = (
        f"mom={momentum_return if momentum_return is None else round(momentum_return,5)} "
        f"imb={book_imbalance if book_imbalance is None else round(book_imbalance,3)} "
        f"-> p_up={prob_up:.3f} conf={confidence:.3f} edge={edge:.3f}"
    )

    return Signal(
        prob_up=prob_up,
        side=side,
        confidence=confidence,
        edge=edge,
        momentum=momentum_return,
        imbalance=book_imbalance,
        market_prob_up=market_prob_up,
        reason=reason,
    )


def should_trade(sig: Signal) -> bool:
    """Gate: only trade when both confidence and edge clear thresholds."""
    if sig.side is None:
        return False
    return sig.confidence >= settings.min_confidence and sig.edge >= settings.min_edge
