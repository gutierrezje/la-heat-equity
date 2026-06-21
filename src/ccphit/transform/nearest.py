import geopandas as gpd
import pandas as pd

from pathlib import Path

from ccphit.common import load_config, write_processed

CRS_M = "EPSG:3310"

def nearest_cooling_center(
    zctas: gpd.GeoDataFrame,
    cooling: gpd.GeoDataFrame
) -> pd.DataFrame:
    zctas = zctas[["zcta", "geometry"]].copy()
    cooling = cooling[["geometry", "site_name", "address"]].copy()

    # meters, not degrees
    zctas_m = zctas.to_crs(CRS_M)
    cooling_m = cooling.to_crs(CRS_M)

    zctas_m["geometry"] = zctas_m.representative_point()

    # nearest neighbor
    nearest = gpd.sjoin_nearest(
        zctas_m,
        cooling_m,
        how="left", 
        distance_col="dist_m"
    )
    nearest = nearest[["zcta", "dist_m", "site_name", "address"]].sort_values("dist_m").drop_duplicates("zcta")
    return nearest

if __name__ == "__main__":
    config = load_config()
    processed_path = Path(config["paths"]["processed"])

    zctas = gpd.read_parquet(processed_path / "zcta_bounds.parquet")
    cooling = gpd.read_parquet(processed_path / "cooling_centers.parquet")

    nearest = nearest_cooling_center(zctas, cooling)
    write_processed(nearest, "zcta_nearest_cooling", config)

    print(nearest["dist_m"].describe())
    print(f"max distance: {nearest['dist_m'].max() / 1000:.2f} km")