"""Tests for breadwinner concentration metric.

Tests cover:
- Per-team breadwinner score computation
- USG% concentration (top-1, top-2, HHI)
- Center position detection
- Quality filter (top-50 O and D)
- Matchup adjustment (variance compression)
- Edge cases (empty data, missing players)
"""

from __future__ import annotations

import pandas as pd
import pytest


# --- Fixtures ---

# A team with high concentration (one dominant player)
CONCENTRATED_TEAM = [
    {
        "player": "Star Player",
        "pos": "Combo G",
        "team": "Concentrated U",
        "mpg": 35.0,
        "usg": 35.0,
        "dbpm": 5.0,
    },
    {
        "player": "Role Player 1",
        "pos": "Wing G",
        "team": "Concentrated U",
        "mpg": 30.0,
        "usg": 15.0,
        "dbpm": 1.0,
    },
    {
        "player": "Role Player 2",
        "pos": "PF/C",
        "team": "Concentrated U",
        "mpg": 28.0,
        "usg": 14.0,
        "dbpm": 0.5,
    },
    {
        "player": "Role Player 3",
        "pos": "C",
        "team": "Concentrated U",
        "mpg": 25.0,
        "usg": 13.0,
        "dbpm": -0.5,
    },
    {
        "player": "Role Player 4",
        "pos": "Scoring PG",
        "team": "Concentrated U",
        "mpg": 20.0,
        "usg": 12.0,
        "dbpm": -1.0,
    },
]

# A team with balanced production
BALANCED_TEAM = [
    {
        "player": "Player A",
        "pos": "Combo G",
        "team": "Balanced U",
        "mpg": 32.0,
        "usg": 20.0,
        "dbpm": 3.0,
    },
    {
        "player": "Player B",
        "pos": "Wing G",
        "team": "Balanced U",
        "mpg": 31.0,
        "usg": 20.0,
        "dbpm": 2.5,
    },
    {
        "player": "Player C",
        "pos": "Stretch 4",
        "team": "Balanced U",
        "mpg": 30.0,
        "usg": 19.0,
        "dbpm": 2.0,
    },
    {"player": "Player D", "pos": "C", "team": "Balanced U", "mpg": 29.0, "usg": 19.0, "dbpm": 1.5},
    {
        "player": "Player E",
        "pos": "Pure PG",
        "team": "Balanced U",
        "mpg": 28.0,
        "usg": 18.0,
        "dbpm": 1.0,
    },
]

# A team with a center as top USG% player
CENTER_DOMINANT = [
    {"player": "Big Man", "pos": "C", "team": "Center Dom", "mpg": 33.0, "usg": 30.0, "dbpm": 6.0},
    {
        "player": "Guard 1",
        "pos": "Combo G",
        "team": "Center Dom",
        "mpg": 30.0,
        "usg": 18.0,
        "dbpm": 2.0,
    },
    {
        "player": "Guard 2",
        "pos": "Wing G",
        "team": "Center Dom",
        "mpg": 28.0,
        "usg": 16.0,
        "dbpm": 1.0,
    },
]


@pytest.fixture
def concentrated_df():
    return pd.DataFrame(CONCENTRATED_TEAM)


@pytest.fixture
def balanced_df():
    return pd.DataFrame(BALANCED_TEAM)


@pytest.fixture
def center_dominant_df():
    return pd.DataFrame(CENTER_DOMINANT)


@pytest.fixture
def combined_player_df():
    """All teams combined."""
    return pd.DataFrame(CONCENTRATED_TEAM + BALANCED_TEAM + CENTER_DOMINANT)


@pytest.fixture
def sample_barttorvik_df():
    """Barttorvik-like team ratings for quality filter testing."""
    return pd.DataFrame(
        [
            # Top-50 in both O and D (eligible)
            {"team": "Concentrated U", "adj_o": 118.0, "adj_d": 90.0, "date": "2025-01-20"},
            {"team": "Balanced U", "adj_o": 115.0, "adj_d": 88.0, "date": "2025-01-20"},
            {"team": "Center Dom", "adj_o": 112.0, "adj_d": 92.0, "date": "2025-01-20"},
            # Bad team (not eligible: poor defense)
            {"team": "Bad D Team", "adj_o": 116.0, "adj_d": 110.0, "date": "2025-01-20"},
            # Bad team (not eligible: poor offense)
            {"team": "Bad O Team", "adj_o": 95.0, "adj_d": 85.0, "date": "2025-01-20"},
        ]
        + [
            # Fill out to 100 teams so ranks are meaningful
            {
                "team": f"Filler {i}",
                "adj_o": 100.0 + i * 0.1,
                "adj_d": 100.0 - i * 0.1,
                "date": "2025-01-20",
            }
            for i in range(100)
        ]
    )


# --- Test: Breadwinner Score Computation ---


class TestComputeBreadwinnerScores:
    """Test per-team breadwinner concentration computation."""

    def test_concentrated_team_high_top1_share(self, concentrated_df):
        from features.sport_specific.ncaab.breadwinner import compute_breadwinner_scores

        scores = compute_breadwinner_scores(concentrated_df, "Concentrated U")
        assert scores is not None
        # 35 / (35+15+14+13+12) = 35/89 ≈ 0.393
        assert scores.top1_usg_share == pytest.approx(35.0 / 89.0, abs=0.001)

    def test_balanced_team_lower_top1_share(self, balanced_df):
        from features.sport_specific.ncaab.breadwinner import compute_breadwinner_scores

        scores = compute_breadwinner_scores(balanced_df, "Balanced U")
        assert scores is not None
        # 20 / (20+20+19+19+18) = 20/96 ≈ 0.208
        assert scores.top1_usg_share == pytest.approx(20.0 / 96.0, abs=0.001)

    def test_concentrated_higher_than_balanced(self, concentrated_df, balanced_df):
        from features.sport_specific.ncaab.breadwinner import compute_breadwinner_scores

        conc = compute_breadwinner_scores(concentrated_df, "Concentrated U")
        bal = compute_breadwinner_scores(balanced_df, "Balanced U")
        assert conc.top1_usg_share > bal.top1_usg_share
        assert conc.usg_hhi > bal.usg_hhi

    def test_top2_share_gt_top1(self, concentrated_df):
        from features.sport_specific.ncaab.breadwinner import compute_breadwinner_scores

        scores = compute_breadwinner_scores(concentrated_df, "Concentrated U")
        assert scores.top2_usg_share > scores.top1_usg_share

    def test_hhi_between_0_and_1(self, concentrated_df, balanced_df):
        from features.sport_specific.ncaab.breadwinner import compute_breadwinner_scores

        for df, team in [(concentrated_df, "Concentrated U"), (balanced_df, "Balanced U")]:
            scores = compute_breadwinner_scores(df, team)
            assert 0.0 < scores.usg_hhi < 1.0

    def test_top1_dbpm_extracted(self, concentrated_df):
        from features.sport_specific.ncaab.breadwinner import compute_breadwinner_scores

        scores = compute_breadwinner_scores(concentrated_df, "Concentrated U")
        # Top USG% player is "Star Player" with dbpm=5.0
        assert scores.top1_dbpm == pytest.approx(5.0)

    def test_empty_df_returns_none(self):
        from features.sport_specific.ncaab.breadwinner import compute_breadwinner_scores

        result = compute_breadwinner_scores(pd.DataFrame(), "Any Team")
        assert result is None

    def test_single_player_returns_none(self):
        from features.sport_specific.ncaab.breadwinner import compute_breadwinner_scores

        df = pd.DataFrame(
            [{"player": "Solo", "pos": "C", "team": "Tiny", "mpg": 30.0, "usg": 25.0, "dbpm": 3.0}]
        )
        result = compute_breadwinner_scores(df, "Tiny")
        assert result is None  # Need at least 2 players

    def test_rotation_size_respected(self, concentrated_df):
        from features.sport_specific.ncaab.breadwinner import compute_breadwinner_scores

        scores = compute_breadwinner_scores(concentrated_df, "Concentrated U", rotation_size=3)
        assert scores is not None
        assert scores.rotation_size == 3


# --- Test: Center Detection ---


class TestCenterDetection:
    """Test center position flag."""

    def test_guard_is_not_center(self, concentrated_df):
        from features.sport_specific.ncaab.breadwinner import compute_breadwinner_scores

        scores = compute_breadwinner_scores(concentrated_df, "Concentrated U")
        assert scores.is_center is False  # "Combo G" is not a center

    def test_center_detected(self, center_dominant_df):
        from features.sport_specific.ncaab.breadwinner import compute_breadwinner_scores

        scores = compute_breadwinner_scores(center_dominant_df, "Center Dom")
        assert scores.is_center is True  # "C" is a center

    def test_pf_c_is_center(self):
        from features.sport_specific.ncaab.breadwinner import compute_breadwinner_scores

        df = pd.DataFrame(
            [
                {
                    "player": "Hybrid Big",
                    "pos": "PF/C",
                    "team": "Test",
                    "mpg": 33.0,
                    "usg": 28.0,
                    "dbpm": 4.0,
                },
                {
                    "player": "Guard",
                    "pos": "Combo G",
                    "team": "Test",
                    "mpg": 30.0,
                    "usg": 18.0,
                    "dbpm": 1.0,
                },
            ]
        )
        scores = compute_breadwinner_scores(df, "Test")
        assert scores.is_center is True


# --- Test: Quality Filter ---


class TestQualityFilter:
    """Test team eligibility based on efficiency rankings."""

    def test_top_team_eligible(self, sample_barttorvik_df):
        from features.sport_specific.ncaab.breadwinner import (
            compute_efficiency_ranks,
            is_breadwinner_eligible,
        )

        ranks = compute_efficiency_ranks(sample_barttorvik_df)
        # "Concentrated U" has adj_o=118, adj_d=90 -> should be top ranks
        assert is_breadwinner_eligible("Concentrated U", ranks, quality_cutoff=50)

    def test_bad_defense_not_eligible(self, sample_barttorvik_df):
        from features.sport_specific.ncaab.breadwinner import (
            compute_efficiency_ranks,
            is_breadwinner_eligible,
        )

        ranks = compute_efficiency_ranks(sample_barttorvik_df)
        # "Bad D Team" has adj_d=110 -> terrible defense, not top-50
        assert not is_breadwinner_eligible("Bad D Team", ranks, quality_cutoff=10)

    def test_unknown_team_not_eligible(self, sample_barttorvik_df):
        from features.sport_specific.ncaab.breadwinner import (
            compute_efficiency_ranks,
            is_breadwinner_eligible,
        )

        ranks = compute_efficiency_ranks(sample_barttorvik_df)
        assert not is_breadwinner_eligible("Nonexistent U", ranks)

    def test_empty_ranks_not_eligible(self):
        from features.sport_specific.ncaab.breadwinner import is_breadwinner_eligible

        assert not is_breadwinner_eligible("Any", pd.DataFrame())


# --- Test: Lookup Builder ---


class TestBuildLookup:
    """Test season-wide breadwinner lookup construction."""

    def test_builds_lookup_for_all_teams(self, combined_player_df, sample_barttorvik_df):
        from features.sport_specific.ncaab.breadwinner import build_breadwinner_lookup

        lookup = build_breadwinner_lookup(
            combined_player_df, sample_barttorvik_df, quality_cutoff=50
        )
        assert "Concentrated U" in lookup
        assert "Balanced U" in lookup
        assert "Center Dom" in lookup

    def test_eligibility_set_by_quality_filter(self, combined_player_df, sample_barttorvik_df):
        from features.sport_specific.ncaab.breadwinner import build_breadwinner_lookup

        lookup = build_breadwinner_lookup(
            combined_player_df, sample_barttorvik_df, quality_cutoff=50
        )
        # Top teams should be eligible
        assert lookup["Concentrated U"].eligible is True
        assert lookup["Balanced U"].eligible is True

    def test_empty_player_df_returns_empty(self, sample_barttorvik_df):
        from features.sport_specific.ncaab.breadwinner import build_breadwinner_lookup

        lookup = build_breadwinner_lookup(pd.DataFrame(), sample_barttorvik_df)
        assert len(lookup) == 0


# --- Test: Matchup Adjustment ---


class TestBreadwinnerAdjustment:
    """Test variance-based probability adjustment."""

    def _make_lookup(self):
        """Helper to create a test lookup."""
        from features.sport_specific.ncaab.breadwinner import BreadwinnerScores

        return {
            "Concentrated U": BreadwinnerScores(
                team="Concentrated U",
                top1_usg_share=0.393,
                top2_usg_share=0.562,
                usg_hhi=0.22,
                top1_dbpm=5.0,
                is_center=False,
                eligible=True,
                rotation_size=5,
            ),
            "Balanced U": BreadwinnerScores(
                team="Balanced U",
                top1_usg_share=0.208,
                top2_usg_share=0.417,
                usg_hhi=0.20,
                top1_dbpm=3.0,
                is_center=False,
                eligible=True,
                rotation_size=5,
            ),
            "Center Dom": BreadwinnerScores(
                team="Center Dom",
                top1_usg_share=0.469,
                top2_usg_share=0.750,
                usg_hhi=0.30,
                top1_dbpm=6.0,
                is_center=True,
                eligible=True,
                rotation_size=3,
            ),
            "Ineligible Team": BreadwinnerScores(
                team="Ineligible Team",
                top1_usg_share=0.35,
                top2_usg_share=0.55,
                usg_hhi=0.25,
                top1_dbpm=2.0,
                is_center=False,
                eligible=False,
                rotation_size=5,
            ),
        }

    def test_concentrated_favorite_sells(self):
        """More concentrated home team as favorite -> negative adjustment."""
        from features.sport_specific.ncaab.breadwinner import get_breadwinner_adjustment

        lookup = self._make_lookup()
        adj = get_breadwinner_adjustment(
            home="Concentrated U",
            away="Balanced U",
            home_prob=0.70,
            lookup=lookup,
            coeff=1.0,
        )
        # bw_score = 0.393 - 0.208 = 0.185 (home more concentrated)
        # adj = 1.0 * (0.5 - 0.7) * 0.185 = -0.037
        assert adj < 0  # Sells the favorite

    def test_concentrated_underdog_buys(self):
        """More concentrated home team as underdog -> positive adjustment."""
        from features.sport_specific.ncaab.breadwinner import get_breadwinner_adjustment

        lookup = self._make_lookup()
        adj = get_breadwinner_adjustment(
            home="Concentrated U",
            away="Balanced U",
            home_prob=0.35,
            lookup=lookup,
            coeff=1.0,
        )
        # bw_score = 0.393 - 0.208 = 0.185 (home more concentrated)
        # adj = 1.0 * (0.5 - 0.35) * 0.185 = +0.0278
        assert adj > 0  # Buys the underdog

    def test_tossup_no_effect(self):
        """At prob=0.5, adjustment should be zero."""
        from features.sport_specific.ncaab.breadwinner import get_breadwinner_adjustment

        lookup = self._make_lookup()
        adj = get_breadwinner_adjustment(
            home="Concentrated U",
            away="Balanced U",
            home_prob=0.50,
            lookup=lookup,
            coeff=1.0,
        )
        assert adj == pytest.approx(0.0, abs=1e-10)

    def test_equal_concentration_no_effect(self):
        """Same team vs same concentration -> zero adjustment."""
        from features.sport_specific.ncaab.breadwinner import get_breadwinner_adjustment

        lookup = self._make_lookup()
        adj = get_breadwinner_adjustment(
            home="Balanced U",
            away="Balanced U",
            home_prob=0.60,
            lookup=lookup,
            coeff=1.0,
        )
        assert adj == pytest.approx(0.0, abs=1e-10)

    def test_missing_team_returns_zero(self):
        """Unknown team -> zero adjustment."""
        from features.sport_specific.ncaab.breadwinner import get_breadwinner_adjustment

        lookup = self._make_lookup()
        adj = get_breadwinner_adjustment(
            home="Unknown",
            away="Balanced U",
            home_prob=0.70,
            lookup=lookup,
            coeff=1.0,
        )
        assert adj == 0.0

    def test_ineligible_team_returns_zero(self):
        """Ineligible team -> zero adjustment."""
        from features.sport_specific.ncaab.breadwinner import get_breadwinner_adjustment

        lookup = self._make_lookup()
        adj = get_breadwinner_adjustment(
            home="Ineligible Team",
            away="Balanced U",
            home_prob=0.70,
            lookup=lookup,
            coeff=1.0,
        )
        assert adj == 0.0

    def test_center_excluded_when_flag_false(self):
        """Center dampening: skip when include_centers=False."""
        from features.sport_specific.ncaab.breadwinner import get_breadwinner_adjustment

        lookup = self._make_lookup()
        adj = get_breadwinner_adjustment(
            home="Center Dom",
            away="Balanced U",
            home_prob=0.70,
            lookup=lookup,
            coeff=1.0,
            include_centers=False,
        )
        assert adj == 0.0

    def test_center_included_when_flag_true(self):
        """Centers included by default."""
        from features.sport_specific.ncaab.breadwinner import get_breadwinner_adjustment

        lookup = self._make_lookup()
        adj = get_breadwinner_adjustment(
            home="Center Dom",
            away="Balanced U",
            home_prob=0.70,
            lookup=lookup,
            coeff=1.0,
            include_centers=True,
        )
        assert adj != 0.0

    def test_top2_variant(self):
        """Using top2 variant changes the adjustment."""
        from features.sport_specific.ncaab.breadwinner import get_breadwinner_adjustment

        lookup = self._make_lookup()
        adj_top1 = get_breadwinner_adjustment(
            home="Concentrated U",
            away="Balanced U",
            home_prob=0.70,
            lookup=lookup,
            coeff=1.0,
            variant="top1",
        )
        adj_top2 = get_breadwinner_adjustment(
            home="Concentrated U",
            away="Balanced U",
            home_prob=0.70,
            lookup=lookup,
            coeff=1.0,
            variant="top2",
        )
        # Both should be negative (selling fav) but different magnitudes
        assert adj_top1 < 0
        assert adj_top2 < 0
        assert adj_top1 != pytest.approx(adj_top2)

    def test_adjustment_is_small_with_small_coeff(self):
        """With realistic coefficient, adjustment should be small."""
        from features.sport_specific.ncaab.breadwinner import get_breadwinner_adjustment

        lookup = self._make_lookup()
        adj = get_breadwinner_adjustment(
            home="Concentrated U",
            away="Balanced U",
            home_prob=0.70,
            lookup=lookup,
            coeff=0.01,
        )
        # Should be very small — not flipping predictions
        assert abs(adj) < 0.01

    def test_known_calculation(self):
        """Verify exact calculation for known inputs."""
        from features.sport_specific.ncaab.breadwinner import get_breadwinner_adjustment

        lookup = self._make_lookup()
        adj = get_breadwinner_adjustment(
            home="Concentrated U",
            away="Balanced U",
            home_prob=0.70,
            lookup=lookup,
            coeff=1.0,
            variant="top1",
        )
        # bw_score = 0.393 - 0.208 = 0.185
        # adj = 1.0 * (0.5 - 0.7) * 0.185 = -0.037
        expected = 1.0 * (0.5 - 0.70) * (0.393 - 0.208)
        assert adj == pytest.approx(expected, abs=0.001)
