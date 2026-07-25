"""Pure-function guards for the exploratory analysis modules.

The figures and the substantive findings are not testable, but the statistics behind them
are — and a concentration index or a VIF that is silently wrong would be worse than no
analysis at all.
"""

import numpy as np
import pandas as pd
import pytest

from ccphit.analysis.equity import (
    classify_priority_cells,
    heat_terciles_are_impossible,
    per_place_vs_per_person,
    priority_population,
)
from ccphit.analysis.structure import name_clusters, variance_inflation

PCTS = ["heat_pct", "svi_pct", "chronic_pct", "resource_gap_pct"]


# --- transparent population categories -----------------------------------------------


def priority_fixture():
    return pd.DataFrame(
        {
            "zcta": [f"Z{i}" for i in range(6)],
            "heat_risk": [2, 3, 4, 2, 3, 4],
            "svi_pct": [10, 20, 30, 70, 80, 90],
            "POP100": [10, 20, 30, 40, 50, 60],
            "draft_score": [99, 1, 50, 80, 40, 20],
        }
    )


def test_priority_cells_assign_every_area_once():
    cells = classify_priority_cells(priority_fixture())
    assert len(cells) == 6
    assert cells[["heat_band", "svi_band"]].notna().all().all()


def test_priority_population_accounts_for_every_resident_once():
    source = priority_fixture()
    summary = priority_population(source)
    assert summary["population"].sum() == source["POP100"].sum()
    assert summary["zctas"].sum() == len(source)
    assert summary["population_share"].sum() == pytest.approx(1.0)


def test_priority_population_does_not_depend_on_composite_score():
    source = priority_fixture()
    original = priority_population(source)
    source["draft_score"] = source["draft_score"].iloc[::-1].to_numpy()
    changed = priority_population(source)
    pd.testing.assert_frame_equal(original, changed)


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
