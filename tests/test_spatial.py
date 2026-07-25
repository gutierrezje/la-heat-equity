"""Spatial graph construction and multiple-testing correction."""

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box

from ccphit.analysis.spatial import benjamini_hochberg, spatial_sample


def test_island_is_separated_without_replacing_mainland_contiguity():
    gdf = gpd.GeoDataFrame(
        {
            "zcta": ["A", "B", "ISLAND"],
            "geometry": [box(0, 0, 1, 1), box(1, 0, 2, 1), box(10, 10, 11, 11)],
        },
        crs="EPSG:3310",
    )
    mainland, islands, weights, note = spatial_sample(gdf)
    assert mainland["zcta"].tolist() == ["A", "B"]
    assert islands["zcta"].tolist() == ["ISLAND"]
    assert weights.neighbors == {0: [1], 1: [0]}
    assert "without invented cross-water neighbors" in note


def test_benjamini_hochberg_matches_known_example():
    adjusted = benjamini_hochberg([0.01, 0.04, 0.03, 0.002])
    assert adjusted == pytest.approx([0.02, 0.04, 0.04, 0.008])


def test_adjusted_values_are_bounded_and_monotonic_when_sorted_by_raw_p():
    raw = np.array([0.20, 0.001, 0.04, 0.9, 0.02])
    adjusted = benjamini_hochberg(raw)
    order = np.argsort(raw)
    assert ((0 <= adjusted) & (adjusted <= 1)).all()
    assert (np.diff(adjusted[order]) >= -1e-12).all()


@pytest.mark.parametrize("bad", [[-0.1], [1.1], [np.nan], [[0.1]]])
def test_benjamini_hochberg_rejects_invalid_p_values(bad):
    with pytest.raises(ValueError, match="p-values"):
        benjamini_hochberg(bad)
