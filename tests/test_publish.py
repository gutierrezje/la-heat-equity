"""Publishing guards. The ArcGIS calls themselves need credentials and are not
covered here; these tests pin the behaviour that must hold *before* any network or
mutation happens.
"""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from ccphit.publish import as_of, connect, describe_local, item_summary, publish


def layer(forecast_date="2026-07-24", n=2):
    cols = {
        "zcta": [f"9000{i}" for i in range(n)],
        "draft_score": [70.0, None],
        "response_category": ["Other short-term snapshot conditions"] * n,
        "response_priority": [0] * n,
        "investment_category": ["Other structural conditions"] * n,
        "investment_priority": [0] * n,
        "historical_heat_er": [20.0] * n,
        "vegetation_shade_pct": [30.0] * n,
    }
    if forecast_date is not None:
        cols["forecast_date"] = [forecast_date] * n
    return gpd.GeoDataFrame(
        cols,
        geometry=[Point(-118.3 + i * 0.01, 34.0) for i in range(n)],
        crs="EPSG:4326",
    )


def test_as_of_reads_a_plain_date_string():
    assert as_of(layer("2026-07-24")) == "2026-07-24"


def test_as_of_normalizes_a_timestamp():
    """GDAL infers a date type when reading GeoJSON back, so this arrives as a
    Timestamp rather than the string that was written."""
    gdf = layer()
    gdf["forecast_date"] = pd.Timestamp("2026-07-24")
    assert as_of(gdf) == "2026-07-24"


def test_as_of_handles_a_missing_column():
    assert as_of(layer(forecast_date=None)) == "unknown"


def test_as_of_takes_the_latest_when_dates_differ():
    gdf = layer(n=2)
    gdf["forecast_date"] = ["2026-06-22", "2026-07-24"]
    assert as_of(gdf) == "2026-07-24"


def test_item_metadata_states_the_two_views_date_and_caveats():
    meta = item_summary(layer("2026-07-24"))
    assert "2026-07-24" in meta["snippet"]
    # the misreading most likely to end up in a public narrative
    assert "intensity, not a count" in meta["description"]
    assert "Short-term response snapshot" in meta["description"]
    assert "not a statement of present conditions" in meta["description"]
    assert "Long-term investment" in meta["description"]
    assert "interpolation" in meta["description"]
    assert "straight-line" in meta["description"]


def test_missing_artifact_tells_you_to_run_the_pipeline(tmp_path):
    config = {"paths": {"processed": str(tmp_path)}}
    with pytest.raises(SystemExit, match="ccphit.run"):
        describe_local(config)


def test_publish_refuses_without_an_item_id_before_touching_the_network(tmp_path):
    """No item id must fail on config alone — never by attempting to authenticate."""
    processed = tmp_path / "processed"
    processed.mkdir()
    layer().to_file(processed / "zcta_scores.geojson", driver="GeoJSON")

    config = {"paths": {"processed": str(processed)}, "publish": {"item_id": ""}}
    with pytest.raises(SystemExit, match="publish.item_id"):
        publish(config, dry_run=True)


def test_connect_requires_credentials_from_the_environment(monkeypatch):
    for var in ("ARCGIS_PROFILE", "ARCGIS_USER", "ARCGIS_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(SystemExit, match="No ArcGIS credentials"):
        connect()
