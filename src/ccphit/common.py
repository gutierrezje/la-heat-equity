import yaml
from shapely.geometry import box
from pathlib import Path

import geopandas as gpd
import pandas as pd

CRS_M = "EPSG:3310"


def pop_weighted_pct(values: pd.Series, pop: pd.Series) -> pd.Series:
    """Percentile rank weighted by population (midpoint rule). Higher value → higher pct.

    Tied values receive the mean percentile of their tie group.
    """
    out = pd.Series(index=values.index, dtype=float)
    valid = values.notna() & pop.notna() & (pop > 0)
    if not valid.any():
        return out
    ranked = pd.DataFrame({"v": values[valid], "p": pop[valid]}).sort_values("v")
    cum = ranked["p"].cumsum()
    ranked["pct"] = (cum - 0.5 * ranked["p"]) / ranked["p"].sum() * 100
    ranked["pct"] = ranked.groupby("v", sort=False)["pct"].transform("mean")
    out.loc[ranked.index] = ranked["pct"]
    return out


def load_config() -> dict:
    with open("config.yml", "r") as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def clip_to_aoi(gdf: gpd.GeoDataFrame, aoi: dict) -> gpd.GeoDataFrame:
    mask = gpd.GeoDataFrame(geometry=[box(*aoi["bbox"])], crs=gdf.crs)
    return gdf.clip(mask)

def write_processed(df: gpd.GeoDataFrame | pd.DataFrame, name: str, config: dict) -> None:
    path = Path(config["paths"]["processed"]) / f"{name}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    print(f"{name}: {df.shape[0]} features -> {path}")