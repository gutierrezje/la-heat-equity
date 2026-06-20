import yaml
from shapely.geometry import box
from pathlib import Path

import geopandas as gpd

def load_config() -> dict:
    with open("config.yml", "r") as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def clip_to_aoi(gdf: gpd.GeoDataFrame, aoi: dict) -> gpd.GeoDataFrame:
    mask = gpd.GeoDataFrame(geometry=[box(*aoi["bbox"])], crs=gdf.crs)
    return gdf.clip(mask)

def write_processed(gdf: gpd.GeoDataFrame, name: str, config: dict) -> None:
    path = Path(config["paths"]["processed"]) / f"{name}.parquet"
    gdf.to_parquet(path)
    print(f"cooling: {gdf.shape[0]} features -> {path}")