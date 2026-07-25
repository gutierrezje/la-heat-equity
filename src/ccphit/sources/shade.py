"""Modeled 2023 summer-day shade by LA County Census block group."""

import geopandas as gpd
import pandas as pd
import requests

from ccphit.config import load_config
from ccphit.io import write_processed

FIELDS = ["GEOID", "tract", "bld15PM", "veg15PM", "total15PM", "CSA"]
PAGE = 2_000
TIMEOUT = 120


class ShadeSchemaError(ValueError):
    """The county shade response does not match the documented layer."""


def normalize_shade(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.empty:
        raise ShadeSchemaError("shade layer returned no features")
    missing = [field for field in [*FIELDS, "geometry"] if field not in gdf.columns]
    if missing:
        raise ShadeSchemaError(f"shade layer missing fields {missing}")

    out = gdf[FIELDS + ["geometry"]].rename(
        columns={
            "GEOID": "block_group_geoid",
            "tract": "tract_geoid",
            "bld15PM": "building_shade_pct",
            "veg15PM": "vegetation_shade_pct",
            "total15PM": "total_shade_pct",
            "CSA": "community",
        }
    )
    geoid = out["block_group_geoid"].astype(str).str.strip()
    invalid = ~geoid.str.fullmatch(r"06037\d{7}")
    if invalid.any():
        raise ShadeSchemaError("invalid LA County block-group GEOID")
    out["block_group_geoid"] = geoid
    if out["block_group_geoid"].duplicated().any():
        raise ShadeSchemaError("shade layer contains duplicate block-group GEOIDs")

    shade_cols = ["building_shade_pct", "vegetation_shade_pct", "total_shade_pct"]
    out[shade_cols] = out[shade_cols].apply(pd.to_numeric, errors="coerce")
    if out[shade_cols].isna().any().any():
        raise ShadeSchemaError("shade percentages contain missing/non-numeric data")
    invalid_pct = (out[shade_cols] < 0) | (out[shade_cols] > 100)
    if invalid_pct.any().any():
        raise ShadeSchemaError("shade percentages must be in [0, 100]")
    return out


def fetch_shade(config: dict) -> gpd.GeoDataFrame:
    url = config["sources"]["shade"]["url"]
    base = {
        "where": "1=1",
        "outFields": ",".join(FIELDS),
        "returnGeometry": "true",
        "outSR": 4326,
        "f": "geojson",
    }
    features = []
    offset = 0
    while True:
        response = requests.get(
            url,
            params={**base, "resultOffset": offset, "resultRecordCount": PAGE},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            message = payload["error"].get("message", str(payload["error"]))
            raise ShadeSchemaError(f"shade service error: {message}")
        page = payload.get("features", [])
        features.extend(page)
        exceeded = payload.get("properties", {}).get("exceededTransferLimit", False)
        if not page or not exceeded:
            break
        offset += len(page)
    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    return normalize_shade(gdf)


if __name__ == "__main__":
    cfg = load_config()
    shade = fetch_shade(cfg)
    write_processed(shade, "shade_block_groups", cfg)
    print(shade.filter(like="shade_pct").describe())
