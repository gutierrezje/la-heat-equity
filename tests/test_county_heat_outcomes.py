"""LA County historical heat-outcome source."""

import pytest

from ccphit.sources.county_heat_outcomes import (
    CountyHeatSchemaError,
    normalize_county_heat,
)


def row(**changes):
    base = {
        "tract": "06037900610",
        "total_pop": 2999,
        "heat_tract": 2.3,
        "heat_cat": 2,
        "svi_score": 19.463,
        "svi_third": 3,
        "heat_risk": "Medium",
    }
    return {**base, **changes}


def test_normalizes_documented_fields():
    out = normalize_county_heat([row()]).iloc[0]
    assert out["tract_geoid"] == "06037900610"
    assert out["historical_heat_er"] == pytest.approx(2.3)
    assert out["historical_heat_tercile"] == 2
    assert out["county_heat_risk"] == "Medium"


def test_rejects_missing_fields_and_bad_geoids():
    missing = row()
    del missing["heat_tract"]
    with pytest.raises(CountyHeatSchemaError, match="missing fields"):
        normalize_county_heat([missing])
    with pytest.raises(CountyHeatSchemaError, match="invalid.*GEOID"):
        normalize_county_heat([row(tract="not-a-tract")])


def test_rejects_duplicate_tracts_and_invalid_categories():
    with pytest.raises(CountyHeatSchemaError, match="duplicate"):
        normalize_county_heat([row(), row()])
    with pytest.raises(CountyHeatSchemaError, match="tercile"):
        normalize_county_heat([row(heat_cat=4)])
