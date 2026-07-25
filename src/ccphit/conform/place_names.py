"""Polygon overlay -> ZCTA grain: a human-readable primary place per ZCTA.

A ZCTA does not respect city lines, so "which city is 90813?" has no single right
answer. Assignment is by the place containing the ZCTA's **population-weighted
centroid** — the same origin D8 uses for cooling-center distance, so "where the
residents effectively are" means one consistent thing across the project. It also
matches how people actually speak: 90813 *is* Long Beach.

`place_name` is therefore a **primary** place, not the only place a ZCTA touches.
`places_touched` records how many it overlaps, so the approximation is visible in the
data rather than buried in a doc.

Labels only — deliberately never used in the score or the crosswalk.
"""

import geopandas as gpd
import pandas as pd

from ccphit.config import CRS_M, load_config
from ccphit.conform.cooling_access import zcta_pop_centroids
from ccphit.io import read_processed, write_processed

# Ignore slivers when counting how many places a ZCTA touches: reprojected boundaries
# clip each other at the edges, and a 0.5% overlap is not a place the ZCTA is "in".
SLIVER_SHARE = 0.005


def assign_place_names(
    zctas: gpd.GeoDataFrame,
    places: gpd.GeoDataFrame,
    tracts: gpd.GeoDataFrame,
) -> pd.DataFrame:
    zctas_m = zctas[["zcta", "geometry"]].to_crs(CRS_M)
    places_m = places[["place_name", "jurisdiction", "geometry"]].to_crs(CRS_M)

    # Primary place: whichever polygon contains the population-weighted centroid.
    centroids = zcta_pop_centroids(tracts, zctas)
    primary = gpd.sjoin(
        centroids, places_m, how="left", predicate="within"
    ).drop_duplicates("zcta")[["zcta", "place_name", "jurisdiction"]]

    # How many places does the ZCTA actually straddle? Honesty about the approximation.
    zctas_m = zctas_m.copy()
    zctas_m["zcta_area"] = zctas_m.geometry.area
    overlap = gpd.overlay(zctas_m, places_m, how="intersection", keep_geom_type=False)
    overlap["share"] = overlap.geometry.area / overlap["zcta_area"]
    touched = (
        overlap[overlap["share"] > SLIVER_SHARE]
        .groupby("zcta")["place_name"]
        .nunique()
        .rename("places_touched")
        .reset_index()
    )

    out = zctas[["zcta"]].merge(primary, on="zcta", how="left", validate="1:1")
    out = out.merge(touched, on="zcta", how="left", validate="1:1")
    out["places_touched"] = out["places_touched"].fillna(0).astype(int)
    return out


if __name__ == "__main__":
    config = load_config()
    zctas = read_processed("zcta_bounds", config, geo=True, require=["zcta"])
    places = read_processed(
        "place_boundaries", config, geo=True, require=["place_name", "jurisdiction"]
    )
    tracts = read_processed("svi_tracts", config, geo=True, require=["pop"])

    named = assign_place_names(zctas, places, tracts)
    write_processed(named, "zcta_place_names", config)

    unnamed = named["place_name"].isna().sum()
    print(f"named: {len(named) - unnamed}/{len(named)} ZCTAs  (unnamed: {unnamed})")
    print(named["jurisdiction"].value_counts(dropna=False).to_string())
    print(f"\nZCTAs straddling >1 place: {(named['places_touched'] > 1).sum()}")
    print(named["places_touched"].describe().round(1).to_string())
