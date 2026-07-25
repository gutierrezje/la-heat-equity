"""Shade aggregation and intervention screen."""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from ccphit.analysis.shade_equity import area_weighted_shade, shade_priority_areas


def test_shade_is_weighted_by_ground_area():
    shade = gpd.GeoDataFrame(
        {
            "building_shade_pct": [0.0, 0.0],
            "vegetation_shade_pct": [10.0, 40.0],
            "total_shade_pct": [10.0, 40.0],
            "geometry": [box(0, 0, 1, 1), box(1, 0, 3, 1)],
        },
        crs="EPSG:3310",
    )
    zctas = gpd.GeoDataFrame(
        {"zcta": ["Z"], "geometry": [box(0, 0, 3, 1)]},
        crs="EPSG:3310",
    )
    out = area_weighted_shade(shade, zctas).iloc[0]
    assert out["vegetation_shade_pct"] == pytest.approx(30.0)


def test_priority_requires_all_three_declared_conditions():
    d = pd.DataFrame(
        {
            "zcta": [f"Z{i}" for i in range(6)],
            "POP100": [10, 20, 30, 40, 50, 60],
            "heat_risk": [1, 2, 3, 4, 4, 4],
            "svi_pct": [10, 20, 30, 70, 80, 90],
            "historical_heat_er": [1, 2, 3, 4, 5, 6],
            "vegetation_shade_pct": [60, 50, 40, 30, 20, 10],
        }
    )
    out = shade_priority_areas(d)
    assert out.loc[out["shade_priority"], "zcta"].tolist() == ["Z4", "Z5"]
