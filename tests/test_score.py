"""The mart: config-driven component scoring (D7)."""

import geopandas as gpd
import pytest
from shapely.geometry import Point

from ccphit.score import score_zctas


def spine(n=4, **cols):
    return gpd.GeoDataFrame(
        {
            "zcta": [f"9000{i}" for i in range(n)],
            "POP100": [1000] * n,
            **cols,
        },
        geometry=[Point(-118.3 + i * 0.01, 34.0) for i in range(n)],
        crs="EPSG:4326",
    )


def config(components):
    return {"score": {"components": components}}


def test_weights_must_sum_to_one():
    cfg = config(
        {
            "heat": {"columns": ["heat_risk"], "weight": 0.5},
            "svi": {"columns": ["svi"], "weight": 0.4},  # sums to 0.9
        }
    )
    with pytest.raises(ValueError, match="must sum to 1"):
        score_zctas(spine(heat_risk=[1, 2, 3, 4], svi=[0.1, 0.2, 0.3, 0.4]), cfg)


def test_single_column_component_is_just_its_own_percentile():
    cfg = config({"heat": {"columns": ["heat_risk"], "weight": 1.0}})
    out = score_zctas(spine(heat_risk=[1, 2, 3, 4]), cfg)

    # equal populations, four distinct values -> midpoints at 12.5/37.5/62.5/87.5
    assert out["heat_pct"].round(1).tolist() == [12.5, 37.5, 62.5, 87.5]
    assert out["draft_score"].equals(out["heat_pct"])


def test_multi_column_component_averages_its_percentiles():
    """The chronic pillar: mean of the condition percentiles, not of raw prevalences."""
    cfg = config(
        {"chronic": {"columns": ["diabetes", "copd"], "weight": 1.0}}
    )
    # diabetes ascending, copd descending -> percentiles cancel to a flat 50
    out = score_zctas(
        spine(diabetes=[1.0, 2.0, 3.0, 4.0], copd=[4.0, 3.0, 2.0, 1.0]), cfg
    )

    assert out["chronic_pct"].round(1).tolist() == [50.0, 50.0, 50.0, 50.0]


def test_a_flat_column_does_not_dominate_the_component_mean():
    """A measure with no spread (asthma-like) contributes a constant 50."""
    cfg = config(
        {"chronic": {"columns": ["diabetes", "asthma"], "weight": 1.0}}
    )
    out = score_zctas(
        spine(diabetes=[1.0, 2.0, 3.0, 4.0], asthma=[9.0, 9.0, 9.0, 9.0]), cfg
    )

    # diabetes percentiles 12.5/37.5/62.5/87.5 averaged with a flat 50
    assert out["chronic_pct"].round(2).tolist() == [31.25, 43.75, 56.25, 68.75]


def test_components_are_combined_by_weight():
    cfg = config(
        {
            "heat": {"columns": ["heat_risk"], "weight": 0.75},
            "svi": {"columns": ["svi"], "weight": 0.25},
        }
    )
    out = score_zctas(spine(heat_risk=[1, 2, 3, 4], svi=[0.4, 0.3, 0.2, 0.1]), cfg)

    expected = 0.75 * out["heat_pct"] + 0.25 * out["svi_pct"]
    assert out["draft_score"].round(6).equals(expected.round(6))


def test_adding_a_pillar_is_a_config_edit_only():
    """Same code path, three pillars then four — no signature or branch changes."""
    three = config(
        {
            "heat": {"columns": ["heat_risk"], "weight": 0.5},
            "svi": {"columns": ["svi"], "weight": 0.3},
            "resource_gap": {"columns": ["dist_m"], "weight": 0.2},
        }
    )
    four = config(
        {
            "heat": {"columns": ["heat_risk"], "weight": 0.25},
            "svi": {"columns": ["svi"], "weight": 0.25},
            "resource_gap": {"columns": ["dist_m"], "weight": 0.25},
            "chronic": {"columns": ["diabetes", "copd"], "weight": 0.25},
        }
    )
    data = dict(
        heat_risk=[1, 2, 3, 4],
        svi=[0.1, 0.2, 0.3, 0.4],
        dist_m=[100.0, 200.0, 300.0, 400.0],
        diabetes=[1.0, 2.0, 3.0, 4.0],
        copd=[1.0, 2.0, 3.0, 4.0],
    )

    a = score_zctas(spine(**data), three)
    b = score_zctas(spine(**data), four)

    assert "chronic_pct" not in a.columns
    assert "chronic_pct" in b.columns
    assert b["draft_score"].notna().all()
