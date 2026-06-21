import pandas as pd
import geopandas as gpd
from pathlib import Path

from ccphit.common import load_config, write_processed

def fetch_svi_tracts(config: dict) -> pd.DataFrame:
    gdb = Path(config["paths"]["raw"]) / config["sources"]["svi"]["gdb"]
    layer = config["sources"]["svi"]["layer"]

    gdf = gpd.read_file(gdb, layer=layer)

    # LA county only
    gdf = gdf[gdf["FIPS"].astype(str).str.startswith(config["aoi"]["county_fips"])]

    # Drop missing sentinel
    gdf = gdf[gdf["RPL_THEMES"] != -999]

    # Keep + rename
    gdf = gdf[["FIPS", "RPL_THEMES", "geometry"]].rename(
        columns={
            "FIPS": "tract_geoid",
            "RPL_THEMES": "svi"
        }
    )
    gdf = gdf.to_crs(epsg=4326)
    return gdf


if __name__ == "__main__":
    config = load_config()
    svi_tracts = fetch_svi_tracts(config)
    write_processed(svi_tracts, "svi_tracts", config)