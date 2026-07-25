"""Artifact reading/writing contracts."""

import geopandas as gpd
import pytest
from shapely.geometry import Point

from ccphit.io import read_processed, write_geojson, write_history, write_processed


@pytest.fixture
def config(tmp_path):
    return {
        "paths": {
            "processed": str(tmp_path / "processed"),
            "history": str(tmp_path / "history"),
        }
    }


@pytest.fixture
def scored():
    return gpd.GeoDataFrame(
        {"zcta": ["90813", "90805"], "draft_score": [75.1, 72.0]},
        geometry=[Point(-118.19, 33.78), Point(-118.18, 33.86)],
        crs="EPSG:4326",
    )


def test_geojson_export_rejects_a_column_list_missing_the_geometry(config, scored):
    """Dropping the active geometry yields a plain DataFrame with no .to_file, so
    fail loudly at the call site instead of with an opaque AttributeError."""
    with pytest.raises(ValueError, match="active geometry"):
        write_geojson(scored, "zcta_scores", config, columns=["zcta", "draft_score"])


def test_geojson_export_accepts_an_explicit_geometry_column(config, scored):
    write_geojson(scored, "zcta_scores", config, columns=["zcta", "geometry"])
    written = gpd.read_file(f"{config['paths']['processed']}/zcta_scores.geojson")
    assert list(written.columns) == ["zcta", "geometry"]
    assert len(written) == 2


def test_processed_roundtrip_preserves_geometry(config, scored):
    write_processed(scored, "zcta_scores", config)
    assert read_processed("zcta_scores", config, geo=True).geometry.notna().all()


def test_history_is_stamped_by_the_date_the_data_describes(config, scored):
    write_history(scored, "heat_scores", config, stamp="2026-07-24")

    from pathlib import Path

    archived = list(Path(config["paths"]["history"]).glob("*.parquet"))
    assert [p.name for p in archived] == ["heat_scores_2026-07-24.parquet"]


def test_rerunning_the_same_forecast_does_not_accumulate_duplicates(config, scored):
    from pathlib import Path

    write_history(scored, "heat_scores", config, stamp="2026-07-24")
    write_history(scored, "heat_scores", config, stamp="2026-07-24")
    write_history(scored, "heat_scores", config, stamp="2026-07-25")

    archived = sorted(p.name for p in Path(config["paths"]["history"]).glob("*.parquet"))
    assert archived == [
        "heat_scores_2026-07-24.parquet",
        "heat_scores_2026-07-25.parquet",
    ]
