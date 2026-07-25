"""CDC/ATSDR Social Vulnerability Index 2022, census tracts — local .gdb, not an API."""

from pathlib import Path

import geopandas as gpd
import pandas as pd

from ccphit.config import load_config
from ccphit.io import write_processed

def fetch_svi_tracts(config: dict) -> pd.DataFrame:
    gdb = Path(config["paths"]["raw"]) / config["sources"]["svi"]["gdb"]
    layer = config["sources"]["svi"]["layer"]

    gdf = gpd.read_file(gdb, layer=layer)

    # LA county only
    gdf = gdf[gdf["FIPS"].astype(str).str.startswith(config["aoi"]["county_fips"])]

    # Drop missing sentinel. Verified that no tract has a valid RPL_THEMES alongside a
    # -999 sub-theme, so this one filter covers the theme columns too.
    gdf = gdf[gdf["RPL_THEMES"] != -999]

    # Keep + rename. The four sub-themes drive the dashboard's SVI-domain breakdown;
    # names follow CDC's documented theme definitions.
    gdf = gdf[
        [
            "FIPS",
            "RPL_THEMES",
            "RPL_THEME1",
            "RPL_THEME2",
            "RPL_THEME3",
            "RPL_THEME4",
            "E_TOTPOP",
            "geometry",
        ]
    ].rename(
        columns={
            "FIPS": "tract_geoid",
            "RPL_THEMES": "svi",
            "RPL_THEME1": "svi_socioeconomic",
            "RPL_THEME2": "svi_household",
            "RPL_THEME3": "svi_minority",
            "RPL_THEME4": "svi_housing_transport",
            "E_TOTPOP": "pop",
        }
    )
    gdf = gdf.to_crs(epsg=4326)
    return gdf


if __name__ == "__main__":
    config = load_config()
    svi_tracts = fetch_svi_tracts(config)
    write_processed(svi_tracts, "svi_tracts", config)