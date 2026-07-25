"""Tract grain -> ZCTA grain: population-weighted areal interpolation.

The engineering centerpiece. Tract values are apportioned to each tract/ZCTA
overlap piece by the population that piece carries, not by its area (see D5, D8).
Intensive variables only — rates and indices, never counts.
"""

import geopandas as gpd

from ccphit.config import CRS_M, load_config
from ccphit.io import read_processed, write_processed


def interpolate_to_zcta(
    tracts: gpd.GeoDataFrame,
    zctas: gpd.GeoDataFrame,
    value_cols: list[str],
) -> gpd.GeoDataFrame:
    """Apportion intensive tract variables onto ZCTAs, weighted by population.

    `value_cols` must all be intensive (rates, indices) — they are averaged, never
    summed. The overlay is the expensive part and is shared across every column, so
    adding a variable costs almost nothing.
    """
    tracts = tracts[["tract_geoid", "pop", "geometry", *value_cols]].copy()
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
    for col in value_cols:
        ix[f"w_{col}"] = ix[col] * ix["w"]

    grouped = ix.groupby("zcta", as_index=False).agg(
        w=("w", "sum"),
        **{f"w_{col}": (f"w_{col}", "sum") for col in value_cols},
    )
    for col in value_cols:
        grouped[col] = grouped[f"w_{col}"] / grouped["w"]

    out = zctas_m.merge(grouped[["zcta", *value_cols]], on="zcta", how="left")
    return out[["zcta", *value_cols, "geometry"]].to_crs(epsg=4326)


if __name__ == "__main__":
    config = load_config()
    zctas = read_processed("zcta_bounds", config, geo=True, require=["zcta"])

    # One pass per configured tract source. The overlay is per-source (each has its own
    # tract geometry and vintage), but the weighting logic is shared — which is what
    # makes the crosswalk a reusable component rather than an SVI-specific script.
    for artifact, spec in config["crosswalk"].items():
        cols = spec["columns"]
        tracts = read_processed(
            artifact, config, geo=True, require=["tract_geoid", "pop", *cols]
        )
        result = interpolate_to_zcta(tracts, zctas, value_cols=cols)
        write_processed(result, spec["output"], config)

        covered = result[cols[0]].notna().sum()
        print(f"  {artifact}: {covered}/{len(result)} ZCTAs covered")
        print(result[cols].describe().round(3).to_string())
