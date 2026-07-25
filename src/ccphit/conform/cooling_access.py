"""Point grain -> ZCTA grain: distance from each ZCTA to its nearest cooling center.

Measured from the ZCTA's population-weighted centroid rather than the polygon, so
the result reads as "typical resident -> nearest center" and stays rankable (D6, D8).
Feeds the score's resource_gap component.
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from ccphit.config import CRS_M, load_config
from ccphit.io import read_processed, write_processed


def zcta_pop_centroids(tracts: gpd.GeoDataFrame, zctas: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Population-weighted center of each ZCTA from tract centroids + E_TOTPOP."""
    tracts = tracts[["pop", "geometry"]].copy()
    zctas = zctas[["zcta", "geometry"]].copy()

    tracts_m = tracts.to_crs(CRS_M)
    zctas_m = zctas.to_crs(CRS_M)

    tracts_m["tract_area"] = tracts_m.geometry.area

    ix = gpd.overlay(
        tracts_m,
        zctas_m,
        how="intersection",
        keep_geom_type=False,
    )
    ix["pop_share"] = ix["pop"] * (ix.geometry.area / ix["tract_area"])
    ix["cx"] = ix.geometry.centroid.x
    ix["cy"] = ix.geometry.centroid.y
    ix["wx"] = ix["cx"] * ix["pop_share"]
    ix["wy"] = ix["cy"] * ix["pop_share"]

    cent = ix.groupby("zcta", as_index=False).agg(
        wx=("wx", "sum"),
        wy=("wy", "sum"),
        pop=("pop_share", "sum"),
    )
    cent["x"] = cent["wx"] / cent["pop"]
    cent["y"] = cent["wy"] / cent["pop"]

    points = gpd.GeoDataFrame(
        cent,
        geometry=[Point(x, y) for x, y in zip(cent["x"], cent["y"])],
        crs=CRS_M,
    )

    # fallback for ZCTAs with no tract overlap (e.g. islands)
    missing = set(zctas_m["zcta"]) - set(points["zcta"])
    if missing:
        fallback = zctas_m[zctas_m["zcta"].isin(missing)].copy()
        fallback["geometry"] = fallback.representative_point()
        points = pd.concat([points, fallback[["zcta", "geometry"]]], ignore_index=True)
        points = gpd.GeoDataFrame(points, geometry="geometry", crs=CRS_M)

    return points[["zcta", "geometry"]]


def nearest_cooling_center(
    zctas: gpd.GeoDataFrame,
    cooling: gpd.GeoDataFrame,
    tracts: gpd.GeoDataFrame,
) -> pd.DataFrame:
    cooling = cooling[["geometry", "site_name", "address"]].copy()
    cooling_m = cooling.to_crs(CRS_M)

    zcta_pts = zcta_pop_centroids(tracts, zctas)

    nearest = gpd.sjoin_nearest(
        zcta_pts,
        cooling_m,
        how="left",
        distance_col="dist_m",
    )
    return nearest[["zcta", "dist_m", "site_name", "address"]].drop_duplicates("zcta")


if __name__ == "__main__":
    config = load_config()
    zctas = read_processed("zcta_bounds", config, geo=True, require=["zcta"])
    cooling = read_processed(
        "cooling_centers", config, geo=True, require=["site_name", "address"]
    )
    tracts = read_processed("svi_tracts", config, geo=True, require=["pop"])

    nearest = nearest_cooling_center(zctas, cooling, tracts)
    write_processed(nearest, "zcta_nearest_cooling", config)

    print(nearest["dist_m"].describe())
    print(f"max distance: {nearest['dist_m'].max() / 1000:.2f} km")
