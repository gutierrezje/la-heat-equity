"""The public ArcGIS categories are simple, deterministic, and filter-ready."""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from ccphit.product import format_product, tercile


def layer():
    return gpd.GeoDataFrame(
        {
            "zcta": [f"Z{i}" for i in range(6)],
            "heat_risk": [4, 4, 3, 2, 1, 1],
            "heat_pct": [95, 90, 70, 50, 30, 10],
            "svi_pct": [95, 75, 65, 45, 25, 5],
            "chronic_pct": [80, 70, 60, 50, 40, 30],
            "historical_heat_er": [60, 50, 40, 30, 20, 10],
            "vegetation_shade_pct": [10, 20, 30, 40, 50, 60],
        },
        geometry=[Point(i, 0) for i in range(6)],
        crs="EPSG:4326",
    )


def test_tercile_reverses_low_shade_so_three_always_means_more_concern():
    values = pd.Series([10, 20, 30, 40, 50, 60])
    assert tercile(values).tolist() == [1, 1, 2, 2, 3, 3]
    assert tercile(values, reverse=True).tolist() == [3, 3, 2, 2, 1, 1]


def test_product_flags_declared_response_and_investment_rules():
    out = format_product(layer())
    assert out.loc[out["response_priority"].eq(1), "zcta"].tolist() == ["Z0", "Z1"]
    assert out.loc[out["investment_priority"].eq(1), "zcta"].tolist() == ["Z0", "Z1"]
    assert (
        out.loc[0, "response_category"]
        == "Extreme heat + high vulnerability"
    )
    assert (
        out.loc[0, "investment_category"]
        == "High harm + high vulnerability + low shade"
    )


def test_response_index_excludes_the_facility_distance_pillar():
    out = format_product(layer())
    assert out.loc[0, "response_index"] == 0.5 * 95 + 0.25 * 95 + 0.25 * 80
