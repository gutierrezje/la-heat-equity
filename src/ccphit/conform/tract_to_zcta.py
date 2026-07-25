"""Tract grain -> ZCTA grain: population-weighted areal interpolation.

The engineering centerpiece. Tract values are apportioned to each tract/ZCTA
overlap piece by the population that piece carries, not by its area (see D5, D8).
Intensive variables only — rates and indices, never counts.
"""

import geopandas as gpd

from ccphit.config import CRS_M, load_config
from ccphit.io import read_processed, write_processed


def interpolate_to_zcta(
    tracts: gpd.GeoDataFrame, zctas: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    tracts = tracts[["tract_geoid", "svi", "pop", "geometry"]].copy()
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
    ix["w"] = ix["pop"] * (ix.geometry.area / ix["tract_area"])
    ix["w_svi"] = ix["svi"] * ix["w"]

    svi_by_zcta = ix.groupby("zcta", as_index=False).agg(
        w_svi=("w_svi", "sum"),
        w=("w", "sum"),
    )
    svi_by_zcta["svi"] = svi_by_zcta["w_svi"] / svi_by_zcta["w"]

    out = zctas_m.merge(svi_by_zcta[["zcta", "svi"]], on="zcta", how="left")
    return out[["zcta", "svi", "geometry"]].to_crs(epsg=4326)


if __name__ == "__main__":
    config = load_config()
    tracts = read_processed(
        "svi_tracts", config, geo=True, require=["tract_geoid", "svi", "pop"]
    )
    zctas = read_processed("zcta_bounds", config, geo=True, require=["zcta"])

    zcta_svi = interpolate_to_zcta(tracts, zctas)
    write_processed(zcta_svi, "zcta_svi", config)

    print(zcta_svi["svi"].describe())
