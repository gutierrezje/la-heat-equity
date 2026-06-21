import geopandas as gpd
import pandas as pd

from pathlib import Path
from tobler.area_weighted import area_interpolate

from ccphit.common import load_config, write_processed

CRS_M = "EPSG:3310"

def tract_to_zcta(tracts: gpd.GeoDataFrame, zctas: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # keep only tracts in LA county
    tracts = tracts[["tract_geoid", "svi", "geometry"]].copy()
    zctas = zctas[["zcta", "geometry"]].copy()

    # project to meters
    tracts_m = tracts.to_crs(CRS_M)
    zctas_m = zctas.to_crs(CRS_M)

    # interpolate svi from tracts to zctas
    result_m = area_interpolate(
        source_df=tracts_m, 
        target_df=zctas_m, 
        intensive_variables=["svi"]
    )

    # reattach zcta from target (same row order)
    result_m["zcta"] = zctas_m["zcta"].values

    # reproject to lat/lon
    result = result_m[["zcta", "svi", "geometry"]].to_crs(epsg=4326)
    return result

if __name__ == "__main__":
    config = load_config()
    processed_path = Path(config["paths"]["processed"])

    tracts = gpd.read_parquet(processed_path / "svi_tracts.parquet")
    zctas = gpd.read_parquet(processed_path / "zcta_bounds.parquet")
    
    zcta_svi = tract_to_zcta(tracts, zctas)
    write_processed(zcta_svi, "zcta_svi", config)

    print(zcta_svi["svi"].describe())