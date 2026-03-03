# tests/test_odds_converter.py
"""Tests for betting/odds_converter.py."""

import pytest
from betting.odds_converter import (
    american_to_implied_prob,
    devig_prob,
)


def test_devig_prob_symmetric_market():
    """Standard -110/-110 market → both sides = 50%."""
    result = devig_prob(-110, -110)
    assert abs(result - 0.5) < 1e-6


def test_devig_prob_sums_to_one():
    """De-vigged home + de-vigged away = 1.0."""
    home = devig_prob(-120, +105)
    away = devig_prob(+105, -120)
    assert abs(home + away - 1.0) < 1e-6


def test_devig_prob_favorite_above_half():
    """-120 favorite de-vigs above 50%."""
    result = devig_prob(-120, +105)
    assert result > 0.5


def test_devig_prob_underdog_below_half():
    """+105 underdog de-vigs below 50%."""
    result = devig_prob(+105, -120)
    assert result < 0.5


def test_devig_prob_lower_than_raw():
    """De-vigged prob is always lower than raw implied prob (vig removed)."""
    raw = american_to_implied_prob(-110)
    fair = devig_prob(-110, -110)
    assert fair < raw


def test_devig_prob_invalid_zero():
    """american=0 should raise ValueError."""
    with pytest.raises(ValueError):
        devig_prob(0, -110)
