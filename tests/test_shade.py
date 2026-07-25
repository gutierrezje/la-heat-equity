"""LA County modeled-shade source."""

import geopandas as gpd
import pytest
from shapely.geometry import box

from ccphit.sources.shade import ShadeSchemaError, normalize_shade


def frame(**changes):
    data = {
        "GEOID": ["060371044041"],
        "tract": ["06037104404"],
        "bld15PM": [2.36],
        "veg15PM": [17.33],
        "total15PM": [19.69],
        "CSA": ["Los Angeles - Pacoima"],
        "geometry": [box(-118.5, 34.0, -118.4, 34.1)],
    }
    data.update(changes)
    return gpd.GeoDataFrame(data, crs="EPSG:4326")


def test_normalizes_shade_fields():
    out = normalize_shade(frame()).iloc[0]
    assert out["block_group_geoid"] == "060371044041"
    assert out["vegetation_shade_pct"] == pytest.approx(17.33)
    assert out["total_shade_pct"] == pytest.approx(19.69)


def test_rejects_invalid_percentages_and_geoids():
    with pytest.raises(ShadeSchemaError, match=r"\[0, 100\]"):
        normalize_shade(frame(total15PM=[101]))
    with pytest.raises(ShadeSchemaError, match="GEOID"):
        normalize_shade(frame(GEOID=["bad"]))
