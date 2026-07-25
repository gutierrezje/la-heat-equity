"""The crosswalk comparison that makes D5/D8 falsifiable rather than asserted."""

import geopandas as gpd
import pytest
from shapely.geometry import box

from ccphit.analysis.crosswalk_validation import area_weighted, centroid_join, compare

LON, LAT = -118.30, 34.00


def cell(i: int, width: int = 1):
    return box(LON + i * 0.01, LAT, LON + (i + width) * 0.01, LAT + 0.01)


def two_tracts(pops, svis, cells=None):
    cells = cells or [cell(0), cell(1)]
    return gpd.GeoDataFrame(
        {
            "tract_geoid": ["A", "B"],
            "svi": svis,
            "pop": pops,
            "geometry": cells,
        },
        crs="EPSG:4326",
    )


def one_zcta(width=2):
    return gpd.GeoDataFrame(
        {"zcta": ["90000"], "POP100": [1000], "geometry": [cell(0, width=width)]},
        crs="EPSG:4326",
    )


def test_area_weighting_ignores_who_lives_there():
    """Equal-area tracts, wildly unequal populations -> a plain 50/50 average."""
    result = area_weighted(two_tracts([100, 1], [1.0, 0.0]), one_zcta())
    assert result["svi_area"].iloc[0] == pytest.approx(0.5, abs=1e-3)


def test_the_two_methods_diverge_exactly_where_population_is_uneven():
    cmp = compare(two_tracts([100, 1], [1.0, 0.0]), one_zcta())

    assert cmp["svi_pop"].iloc[0] == pytest.approx(100 / 101, abs=1e-6)
    assert cmp["svi_area"].iloc[0] == pytest.approx(0.5, abs=1e-3)
    # the shipped method reports much higher vulnerability than the naive one
    assert cmp["diff_area"].iloc[0] > 0.4


def test_the_two_methods_agree_when_population_is_even():
    """No population gradient, no disagreement — the comparison isn't rigged."""
    cmp = compare(two_tracts([100, 100], [1.0, 0.0]), one_zcta())
    assert cmp["diff_area"].iloc[0] == pytest.approx(0.0, abs=1e-3)


def test_centroid_join_can_leave_a_zcta_with_no_value():
    """Its decisive flaw: coverage holes, not just inaccuracy.

    A ZCTA containing no tract centroid gets nothing at all — 17 of 294 in the real
    data. Here the tracts sit either side of the ZCTA's own footprint.
    """
    tracts = two_tracts([100, 100], [1.0, 0.0], cells=[cell(0), cell(4)])
    zctas = gpd.GeoDataFrame(
        {"zcta": ["90000"], "POP100": [1000], "geometry": [cell(2)]},
        crs="EPSG:4326",
    )

    joined = centroid_join(tracts, zctas)
    assert joined.empty  # nothing assigned

    cmp = compare(tracts, zctas)
    assert cmp["svi_centroid"].isna().all()


def test_compare_keeps_one_row_per_zcta_with_geometry():
    cmp = compare(two_tracts([100, 1], [1.0, 0.0]), one_zcta())
    assert len(cmp) == 1
    assert cmp.geometry.notna().all()
    for col in ("svi_pop", "svi_area", "svi_centroid", "diff_area", "diff_centroid"):
        assert col in cmp.columns
