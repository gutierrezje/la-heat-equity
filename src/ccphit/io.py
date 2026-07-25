"""Reading and writing the `data/processed/` artifacts each stage exchanges.

Artifact names are the contract between pipeline stages and the published ArcGIS
layer — they are deliberately independent of the module names that produce them.
"""

from collections.abc import Iterable
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd

from ccphit.config import processed_dir


class StaleArtifactError(Exception):
    """A stored artifact predates the current pipeline and must be regenerated."""


def read_processed(
    name: str,
    config: dict,
    geo: bool = False,
    require: Iterable[str] = (),
) -> pd.DataFrame:
    """Load a processed artifact, asserting the columns this stage depends on.

    `require` makes each stage's input contract explicit, so resuming with
    `--from` onto artifacts written by an older version of the pipeline fails
    immediately with a fixable message rather than a KeyError several stages
    later — after partial output has already been written.
    """
    path = processed_dir(config) / f"{name}.parquet"
    df = gpd.read_parquet(path) if geo else pd.read_parquet(path)

    missing = [c for c in require if c not in df.columns]
    if missing:
        raise StaleArtifactError(
            f"{path} is missing {missing}; it was written by an older version of the "
            f"pipeline (found columns: {list(df.columns)}). Regenerate it with a full "
            f"run: uv run python -m ccphit.run"
        )
    return df


def pull_stamp() -> str:
    """Today's date, for live sources that carry no date of their own.

    CalHeatScore stamps its own forecast date; the ArcGIS feature services do not,
    so the best available provenance is when we pulled them.
    """
    return date.today().isoformat()


def write_history(
    df: gpd.GeoDataFrame | pd.DataFrame, name: str, config: dict, stamp: str
) -> None:
    """Archive a dated copy of a snapshot that cannot be re-fetched later.

    Stamped with the date the data describes, not the wall clock, so re-running on
    the same forecast is idempotent rather than accumulating duplicates.
    """
    path = Path(config["paths"]["history"]) / f"{name}_{stamp}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    print(f"{name}: archived {stamp} -> {path}")


def write_processed(df: gpd.GeoDataFrame | pd.DataFrame, name: str, config: dict) -> None:
    path = processed_dir(config) / f"{name}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    print(f"{name}: {df.shape[0]} features -> {path}")


def write_geojson(
    gdf: gpd.GeoDataFrame,
    name: str,
    config: dict,
    columns: list[str] | None = None,
) -> None:
    path = processed_dir(config) / f"{name}.geojson"
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is not None and gdf.geometry.name not in columns:
        raise ValueError(
            f"{name}.geojson: columns must include the active geometry column "
            f"{gdf.geometry.name!r}; got {columns!r}"
        )
    out = gdf[columns] if columns is not None else gdf
    out.to_file(path, driver="GeoJSON")
    print(f"{name}: {len(out)} features -> {path}")
