"""Polygon overlay -> ZCTA grain: medically-underserved designation per ZCTA.

Emits two views of the same overlay, because a ZCTA rarely sits neatly inside or
outside a designation boundary:

  `in_mua`         does the typical resident live in a designated MUA? Point-in-polygon
                   against the ZCTA's population-weighted centroid, the same origin D8
                   uses for cooling-center distance. Good for map symbology.
  `mua_area_share` fraction of the ZCTA's area inside a designation. Keeps the nuance
                   a boolean throws away, for popups and charts.

Context only — this is deliberately **not** a score component. The proposal never had
healthcare shortage in the composite formula, and adding a fifth pillar is a
methodology change to discuss with a mentor, not a side effect of wiring a source.
"""

import geopandas as gpd
import pandas as pd

from ccphit.config import CRS_M, load_config
from ccphit.conform.cooling_access import zcta_pop_centroids
from ccphit.io import read_processed, write_processed


def designate_zctas(
    zctas: gpd.GeoDataFrame,
    mua: gpd.GeoDataFrame,
    tracts: gpd.GeoDataFrame,
) -> pd.DataFrame:
    zctas_m = zctas[["zcta", "geometry"]].to_crs(CRS_M)
    mua_m = mua[["geometry"]].to_crs(CRS_M)

    # Designations overlap each other; dissolve so shares cannot exceed 1.
    mua_union = mua_m.union_all()

    zctas_m = zctas_m.copy()
    zctas_m["zcta_area"] = zctas_m.geometry.area
    zctas_m["mua_area"] = zctas_m.geometry.intersection(mua_union).area
    zctas_m["mua_area_share"] = (zctas_m["mua_area"] / zctas_m["zcta_area"]).clip(0, 1)

    centroids = zcta_pop_centroids(tracts, zctas)
    centroids = centroids.copy()
    centroids["in_mua"] = centroids.geometry.within(mua_union)

    out = zctas_m[["zcta", "mua_area_share"]].merge(
        centroids[["zcta", "in_mua"]], on="zcta", how="left", validate="1:1"
    )
    out["in_mua"] = out["in_mua"].fillna(False)
    return out


if __name__ == "__main__":
    config = load_config()
    zctas = read_processed("zcta_bounds", config, geo=True, require=["zcta"])
    mua = read_processed("mua_areas", config, geo=True)
    tracts = read_processed("svi_tracts", config, geo=True, require=["pop"])

    designated = designate_zctas(zctas, mua, tracts)
    write_processed(designated, "zcta_underservice", config)

    n = int(designated["in_mua"].sum())
    print(f"in_mua: {n}/{len(designated)} ZCTAs")
    print(designated["mua_area_share"].describe().round(3).to_string())
