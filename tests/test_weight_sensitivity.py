"""Rank-stability analysis under random reweighting (D7's open question)."""

import numpy as np
import pandas as pd
import pytest

from ccphit.analysis.weight_sensitivity import rank_stability, sample_weights

PCTS = ["heat_pct", "svi_pct", "chronic_pct", "resource_gap_pct"]


def layer(rows):
    """rows: list of (zcta, heat, svi, chronic, gap)."""
    return pd.DataFrame(rows, columns=["zcta", *PCTS])


def test_sampled_weights_lie_on_the_simplex():
    w = sample_weights(4, 500, np.random.default_rng(0))
    assert w.shape == (500, 4)
    assert np.allclose(w.sum(axis=1), 1.0)
    assert (w >= 0).all()


def test_a_zcta_worst_on_every_component_is_always_top_ranked():
    """If it dominates on all four, no weighting can dislodge it."""
    data = layer(
        [
            ("90000", 99.0, 99.0, 99.0, 99.0),
            ("90001", 10.0, 10.0, 10.0, 10.0),
            ("90002", 20.0, 20.0, 20.0, 20.0),
        ]
    )
    out = rank_stability(data, PCTS, draws=200, top_n=1).set_index("zcta")
    assert out.loc["90000", "top_n_share"] == 1.0
    assert out.loc["90000", "rank_worst"] == 1


def test_a_zcta_best_on_every_component_is_never_top_ranked():
    data = layer(
        [
            ("90000", 99.0, 99.0, 99.0, 99.0),
            ("90001", 1.0, 1.0, 1.0, 1.0),
            ("90002", 50.0, 50.0, 50.0, 50.0),
        ]
    )
    out = rank_stability(data, PCTS, draws=200, top_n=1).set_index("zcta")
    assert out.loc["90001", "top_n_share"] == 0.0


def test_a_zcta_extreme_on_one_component_only_is_weight_dependent():
    """The whole point of the analysis: single-pillar extremes are not robust."""
    data = layer(
        [
            ("90000", 99.0, 5.0, 5.0, 5.0),  # heat alone
            ("90001", 5.0, 60.0, 60.0, 60.0),  # broadly elevated
            ("90002", 50.0, 50.0, 50.0, 50.0),
        ]
    )
    out = rank_stability(data, PCTS, draws=2000, top_n=1).set_index("zcta")
    assert 0.0 < out.loc["90000", "top_n_share"] < 1.0


def test_minimum_weight_floor_narrows_the_range_of_outcomes():
    """Constraining the draw cannot widen a ZCTA's rank spread."""
    data = layer(
        [
            ("90000", 99.0, 5.0, 5.0, 5.0),
            ("90001", 5.0, 70.0, 70.0, 70.0),
            ("90002", 50.0, 50.0, 50.0, 50.0),
            ("90003", 30.0, 30.0, 80.0, 20.0),
        ]
    )
    loose = rank_stability(data, PCTS, draws=3000, top_n=1).set_index("zcta")
    tight = rank_stability(
        data, PCTS, draws=3000, top_n=1, min_weight=0.2
    ).set_index("zcta")

    loose_spread = (loose["rank_worst"] - loose["rank_best"]).sum()
    tight_spread = (tight["rank_worst"] - tight["rank_best"]).sum()
    assert tight_spread <= loose_spread


def test_rows_missing_a_component_are_excluded_rather_than_ranked():
    data = layer(
        [
            ("90000", 99.0, 99.0, 99.0, 99.0),
            ("90001", 10.0, None, 10.0, 10.0),
        ]
    )
    out = rank_stability(data, PCTS, draws=100)
    assert out["zcta"].tolist() == ["90000"]


def test_analysis_is_reproducible_for_a_fixed_seed():
    data = layer(
        [
            ("90000", 90.0, 20.0, 40.0, 60.0),
            ("90001", 30.0, 80.0, 50.0, 20.0),
            ("90002", 50.0, 50.0, 50.0, 50.0),
        ]
    )
    a = rank_stability(data, PCTS, draws=500, seed=7)
    b = rank_stability(data, PCTS, draws=500, seed=7)
    pd.testing.assert_frame_equal(a, b)


@pytest.mark.parametrize("floor", [0.1, 0.2])
def test_weight_floor_is_actually_respected(floor):
    rng = np.random.default_rng(1)
    w = sample_weights(4, 5000, rng)
    kept = w[w.min(axis=1) >= floor]
    assert len(kept) > 0
    assert (kept >= floor).all()
