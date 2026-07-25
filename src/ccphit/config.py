"""Project configuration and the spatial scope it defines."""

from pathlib import Path

import geopandas as gpd
import yaml
from shapely.geometry import box

# Projected CRS (meters) for all area/distance math. Geographic work stays in EPSG:4326.
CRS_M = "EPSG:3310"


def load_config() -> dict:
    with open("config.yml", "r") as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def processed_dir(config: dict) -> Path:
    return Path(config["paths"]["processed"])


def clip_to_aoi(gdf: gpd.GeoDataFrame, aoi: dict) -> gpd.GeoDataFrame:
    mask = gpd.GeoDataFrame(geometry=[box(*aoi["bbox"])], crs=gdf.crs)
    return gdf.clip(mask)
