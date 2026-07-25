"""Reading and writing the `data/processed/` artifacts each stage exchanges.

Artifact names are the contract between pipeline stages and the published ArcGIS
layer — they are deliberately independent of the module names that produce them.
"""

import geopandas as gpd
import pandas as pd

from ccphit.config import processed_dir


def read_processed(name: str, config: dict, geo: bool = False) -> pd.DataFrame:
    path = processed_dir(config) / f"{name}.parquet"
    return gpd.read_parquet(path) if geo else pd.read_parquet(path)


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
    out = gdf[columns] if columns is not None else gdf
    out.to_file(path, driver="GeoJSON")
    print(f"{name}: {len(out)} features -> {path}")
