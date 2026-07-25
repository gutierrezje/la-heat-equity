"""Pure-function guards for the exploratory analysis modules.

The figures and the substantive findings are not testable, but the statistics behind them
are — and a concentration index or a VIF that is silently wrong would be worse than no
analysis at all.
"""

import numpy as np
import pandas as pd
import pytest

from ccphit.analysis.equity import (
    concentration,
    heat_terciles_are_impossible,
    per_place_vs_per_person,
)
from ccphit.analysis.structure import name_clusters, variance_inflation

PCTS = ["heat_pct", "svi_pct", "chronic_pct", "resource_gap_pct"]


# --- concentration -------------------------------------------------------------------


def test_evenly_spread_risk_has_a_concentration_index_of_zero():
    d = pd.DataFrame({"draft_score": [50.0] * 4, "POP100": [100] * 4})
    _, _, idx = concentration(d, "draft_score", "POP100")
    assert idx == pytest.approx(0.0, abs=1e-9)


def test_risk_borne_by_a_tiny_group_gives_a_high_concentration_index():
    # one small ZCTA carries all the risk
    d = pd.DataFrame({"draft_score": [100.0, 0.0, 0.0, 0.0], "POP100": [1, 100, 100, 100]})
    _, _, idx = concentration(d, "draft_score", "POP100")
    assert idx > 0.9


def test_concentration_curve_starts_at_origin_and_ends_at_one():
    d = pd.DataFrame({"draft_score": [80.0, 40.0, 10.0], "POP100": [10, 20, 30]})
    x, y, _ = concentration(d, "draft_score", "POP100")
    assert (x[0], y[0]) == (0.0, 0.0)
    assert x[-1] == pytest.approx(1.0)
    assert y[-1] == pytest.approx(1.0)


def test_concentration_curve_is_monotonically_increasing():
    rng = np.random.default_rng(3)
    d = pd.DataFrame(
        {"draft_score": rng.uniform(0, 100, 40), "POP100": rng.integers(100, 9000, 40)}
    )
    x, y, _ = concentration(d, "draft_score", "POP100")
    assert (np.diff(x) >= 0).all()
    assert (np.diff(y) >= -1e-12).all()


# --- per place vs per person ---------------------------------------------------------


def test_population_weighting_shifts_the_mean_toward_populous_places():
    d = pd.DataFrame({"svi_pct": [10.0, 90.0], "POP100": [10, 1000]})
    out = per_place_vs_per_person(d, ["svi_pct"]).iloc[0]
    assert out["per_place"] == pytest.approx(50.0)
    assert out["per_person"] > 88  # dominated by the populous, high-SVI place
    assert out["difference"] > 0


def test_equal_populations_make_the_two_means_identical():
    d = pd.DataFrame({"svi_pct": [10.0, 90.0], "POP100": [500, 500]})
    out = per_place_vs_per_person(d, ["svi_pct"]).iloc[0]
    assert out["difference"] == pytest.approx(0.0)


# --- saturation detection ------------------------------------------------------------


def test_saturated_heat_is_detected_as_untercileable():
    """The real failure: one tie group spanning the 33rd to 66th percentile."""
    saturated = pd.Series([10.0] + [54.4] * 20 + [90.0])
    assert heat_terciles_are_impossible(saturated)


def test_well_spread_heat_can_be_binned():
    assert not heat_terciles_are_impossible(pd.Series(np.linspace(0, 100, 60)))


# --- VIF ----------------------------------------------------------------------------


def test_orthogonal_columns_have_vif_near_one():
    rng = np.random.default_rng(11)
    X = rng.normal(size=(400, 3))
    assert max(variance_inflation(X)) < 1.3


def test_a_duplicated_column_produces_a_large_vif():
    rng = np.random.default_rng(11)
    a = rng.normal(size=400)
    X = np.column_stack([a, a + rng.normal(scale=0.02, size=400), rng.normal(size=400)])
    vifs = variance_inflation(X)
    assert vifs[0] > 20 and vifs[1] > 20
    assert vifs[2] < 1.5  # the independent column is unaffected


# --- cluster naming -----------------------------------------------------------------


def test_clusters_are_named_from_their_profile_not_their_arbitrary_id():
    """k-means ids change with the seed, so labels must derive from the shape."""
    profiles = pd.DataFrame(
        {
            "heat_pct": [41.9, 63.0, 69.2, 11.5],
            "svi_pct": [76.1, 39.5, 25.4, 16.0],
            "chronic_pct": [72.3, 47.3, 31.1, 22.3],
            "resource_gap_pct": [32.2, 83.9, 44.6, 55.3],
        },
        index=[0, 1, 2, 3],
    )
    names = name_clusters(profiles, PCTS)
    assert names[0] == "urban_vulnerable"
    assert names[1] == "access_limited"
    assert names[2] == "hot_not_vulnerable"
    assert names[3] == "lower_risk"


def test_cluster_naming_is_invariant_to_row_order():
    profiles = pd.DataFrame(
        {
            "heat_pct": [11.5, 69.2, 41.9],
            "svi_pct": [16.0, 25.4, 76.1],
            "chronic_pct": [22.3, 31.1, 72.3],
            "resource_gap_pct": [55.3, 44.6, 32.2],
        },
        index=[7, 2, 5],
    )
    names = name_clusters(profiles, PCTS)
    assert names == {7: "lower_risk", 2: "hot_not_vulnerable", 5: "urban_vulnerable"}
