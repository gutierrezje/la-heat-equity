"""Grain reconciliation: tract -> ZCTA interpolation (D5/D8) and ZIP -> ZCTA (D4)."""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from ccphit.conform.tract_to_zcta import interpolate_to_zcta
from ccphit.conform.underservice import designate_zctas
from ccphit.conform.zip_to_zcta import attach_heat_scores

# Real LA-area coordinates: EPSG:3310 is California Albers, so synthetic geometry
# near (0, 0) would project into nonsense.
LON, LAT = -118.30, 34.00


def cell(i: int, width: int = 1) -> box:
    """A 0.01-degree tall box, `width` cells wide, starting at column `i`."""
    return box(LON + i * 0.01, LAT, LON + (i + width) * 0.01, LAT + 0.01)


def test_interpolation_weights_by_population_not_area():
    """The methodology test.

    Two tracts of equal area, both wholly inside one ZCTA, with wildly different
    populations. Area-weighting would average the SVI values to 0.5; population
    weighting must pull the result almost all the way to the populous tract.
    """
    tracts = gpd.GeoDataFrame(
        {
            "tract_geoid": ["A", "B"],
            "svi": [1.0, 0.0],
            "pop": [100, 1],
            "geometry": [cell(0), cell(1)],
        },
        crs="EPSG:4326",
    )
    zctas = gpd.GeoDataFrame(
        {"zcta": ["90000"], "geometry": [cell(0, width=2)]}, crs="EPSG:4326"
    )

    result = interpolate_to_zcta(tracts, zctas, value_cols=["svi"])

    assert len(result) == 1
    # population-weighted: (1.0*100 + 0.0*1) / 101
    assert result["svi"].iloc[0] == pytest.approx(100 / 101)
    # and emphatically not the area-weighted answer
    assert abs(result["svi"].iloc[0] - 0.5) > 0.4


def test_partial_overlap_contributes_proportional_population():
    """A tract half inside the ZCTA should bring half its population to the average."""
    tracts = gpd.GeoDataFrame(
        {
            "tract_geoid": ["A", "B"],
            "svi": [1.0, 0.0],
            "pop": [100, 100],
            # A lies fully inside the ZCTA; B straddles its edge, half in / half out.
            "geometry": [cell(0), cell(1, width=2)],
        },
        crs="EPSG:4326",
    )
    zctas = gpd.GeoDataFrame(
        {"zcta": ["90000"], "geometry": [cell(0, width=2)]}, crs="EPSG:4326"
    )

    svi = interpolate_to_zcta(tracts, zctas, value_cols=["svi"])["svi"].iloc[0]

    # weights: A = 100, B = 100 * 0.5 -> (1.0*100 + 0.0*50) / 150
    assert svi == pytest.approx(100 / 150, abs=1e-3)


def test_zcta_with_no_overlapping_tract_is_left_as_no_data():
    tracts = gpd.GeoDataFrame(
        {
            "tract_geoid": ["A"],
            "svi": [1.0],
            "pop": [100],
            "geometry": [cell(0)],
        },
        crs="EPSG:4326",
    )
    zctas = gpd.GeoDataFrame(
        {
            "zcta": ["90000", "90001"],
            "geometry": [cell(0), box(LON + 1, LAT + 1, LON + 1.01, LAT + 1.01)],
        },
        crs="EPSG:4326",
    )

    result = interpolate_to_zcta(tracts, zctas, value_cols=["svi"]).set_index("zcta")

    assert result.loc["90000", "svi"] == 1.0
    assert pd.isna(result.loc["90001", "svi"])


def test_multiple_value_columns_share_one_overlay():
    """Adding a variable must not change how any other variable is weighted."""
    tracts = gpd.GeoDataFrame(
        {
            "tract_geoid": ["A", "B"],
            "svi": [1.0, 0.0],
            "svi_household": [0.0, 1.0],  # deliberately inverted
            "pop": [100, 1],
            "geometry": [cell(0), cell(1)],
        },
        crs="EPSG:4326",
    )
    zctas = gpd.GeoDataFrame(
        {"zcta": ["90000"], "geometry": [cell(0, width=2)]}, crs="EPSG:4326"
    )

    both = interpolate_to_zcta(
        tracts, zctas, value_cols=["svi", "svi_household"]
    )
    alone = interpolate_to_zcta(tracts, zctas, value_cols=["svi"])

    assert both["svi"].iloc[0] == pytest.approx(alone["svi"].iloc[0])
    assert both["svi"].iloc[0] == pytest.approx(100 / 101)
    assert both["svi_household"].iloc[0] == pytest.approx(1 / 101)


def _tracts_covering(cells):
    """One tract per cell, equal population, so the centroid lands mid-ZCTA."""
    return gpd.GeoDataFrame(
        {
            "tract_geoid": [str(i) for i in range(len(cells))],
            "pop": [100] * len(cells),
            "geometry": cells,
        },
        crs="EPSG:4326",
    )


def test_zcta_fully_inside_a_designation_is_fully_underserved():
    zctas = gpd.GeoDataFrame(
        {"zcta": ["90000"], "geometry": [cell(1)]}, crs="EPSG:4326"
    )
    mua = gpd.GeoDataFrame({"geometry": [cell(0, width=3)]}, crs="EPSG:4326")

    out = designate_zctas(zctas, mua, _tracts_covering([cell(1)])).set_index("zcta")

    assert bool(out.loc["90000", "in_mua"]) is True
    # Tolerance is 1e-3, not 1e-6: reprojecting two lat/lon boxes of different widths
    # to EPSG:3310 makes the wider one's straight chord sag away from the narrower
    # one's along the shared parallel, leaving a ~0.01% sliver.
    assert out.loc["90000", "mua_area_share"] == pytest.approx(1.0, abs=1e-3)


def test_zcta_outside_every_designation_is_not_underserved():
    zctas = gpd.GeoDataFrame(
        {"zcta": ["90000"], "geometry": [cell(0)]}, crs="EPSG:4326"
    )
    mua = gpd.GeoDataFrame({"geometry": [cell(5)]}, crs="EPSG:4326")

    out = designate_zctas(zctas, mua, _tracts_covering([cell(0)])).set_index("zcta")

    assert bool(out.loc["90000", "in_mua"]) is False
    assert out.loc["90000", "mua_area_share"] == pytest.approx(0.0, abs=1e-6)


def test_partially_designated_zcta_reports_a_fractional_share():
    """A boolean would throw this away, which is why both views are emitted."""
    zctas = gpd.GeoDataFrame(
        {"zcta": ["90000"], "geometry": [cell(0, width=2)]}, crs="EPSG:4326"
    )
    mua = gpd.GeoDataFrame({"geometry": [cell(0)]}, crs="EPSG:4326")

    out = designate_zctas(zctas, mua, _tracts_covering([cell(0, width=2)]))

    assert out["mua_area_share"].iloc[0] == pytest.approx(0.5, abs=1e-3)


def test_overlapping_designations_cannot_exceed_full_coverage():
    """HRSA designations overlap each other; without a union the share would double."""
    zctas = gpd.GeoDataFrame(
        {"zcta": ["90000"], "geometry": [cell(0, width=2)]}, crs="EPSG:4326"
    )
    mua = gpd.GeoDataFrame(
        {"geometry": [cell(0, width=2), cell(0, width=2)]}, crs="EPSG:4326"
    )

    out = designate_zctas(zctas, mua, _tracts_covering([cell(0, width=2)]))

    assert out["mua_area_share"].iloc[0] == pytest.approx(1.0, abs=1e-6)


def test_unmatched_zips_stay_no_data_rather_than_being_imputed():
    """D4: ZIP and ZCTA are distinct systems; a miss is a miss."""
    zctas = gpd.GeoDataFrame(
        {
            "zcta": ["90813", "91125"],  # 91125 is Caltech - no residential forecast
            "POP100": [54565, 0],
            "geometry": [cell(0), cell(2)],
        },
        crs="EPSG:4326",
    )
    heat = pd.DataFrame(
        {"zip": ["90813"], "forecast_date": ["2026-07-24"], "heat_risk": [4]}
    )

    merged = attach_heat_scores(zctas, heat).set_index("zcta")

    assert merged.loc["90813", "heat_risk"] == 4
    assert pd.isna(merged.loc["91125", "heat_risk"])
    assert "zip" not in merged.columns


def test_heat_join_preserves_the_zcta_spine():
    """The join must never add or drop ZCTAs (score.py asserts on this downstream)."""
    zctas = gpd.GeoDataFrame(
        {
            "zcta": ["90813", "90802", "90805"],
            "POP100": [54565, 33000, 95350],
            "geometry": [cell(0), cell(2), cell(4)],
        },
        crs="EPSG:4326",
    )
    heat = pd.DataFrame(
        {
            "zip": ["90813", "90805"],
            "forecast_date": ["2026-07-24"] * 2,
            "heat_risk": [4, 4],
        }
    )

    assert len(attach_heat_scores(zctas, heat)) == 3
