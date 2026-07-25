"""LA County and ZCTA boundary polygons — the spatial spine every source lands on.

Scope is defined by the county polygon, not the config bbox: the bbox is only a
coarse server-side pre-filter (see D2).
"""

import geopandas as gpd
import requests

from ccphit.config import load_config
from ccphit.io import pull_stamp, write_history, write_processed


def fetch_county_boundary(config: dict) -> gpd.GeoDataFrame:
    url = config["sources"]["county_boundary"]["url"]
    params = {
        "where": f"GEOID = '{config['aoi']['county_fips']}'",
        "outFields": "GEOID, NAME",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise Exception(data["error"]["message"])
    return gpd.GeoDataFrame.from_features(data["features"], crs="EPSG:4326")


def fetch_zcta(config: dict, bbox: list) -> gpd.GeoDataFrame:
    url = config["sources"]["zcta"]["url"]
    params = {
        "geometry": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "where": "1=1",
        "outFields": "ZCTA5, GEOID, POP100",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "geojson",
    }
    features = []
    offset = 0
    while True:
        response = requests.get(url, params={**params, "resultOffset": offset})
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise Exception(data["error"]["message"])
        if len(data["features"]) == 0:
            break
        features.extend(data["features"])
        offset += len(data["features"])

    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    gdf["ZCTA5"] = gdf["ZCTA5"].astype(str).str.zfill(5)
    gdf = gdf[["ZCTA5", "geometry", "POP100"]]
    return gdf.rename(columns={"ZCTA5": "zcta"})


def la_county_zctas(config: dict) -> gpd.GeoDataFrame:
    county_boundary = fetch_county_boundary(config)
    county_geometry = county_boundary.geometry.union_all()
    minx, miny, maxx, maxy = county_geometry.bounds
    pad = 0.01
    bbox = [minx - pad, miny - pad, maxx + pad, maxy + pad]

    zcta = fetch_zcta(config, bbox)
    return zcta[zcta.representative_point().within(county_geometry)].copy()


if __name__ == "__main__":
    config = load_config()
    zcta_bounds = la_county_zctas(config)
    write_processed(zcta_bounds, "zcta_bounds", config)

    # Also a live service. Observed stable across the 2026-06-22 and 2026-07-24
    # pulls (POP100 and the ZCTA set were bit-identical), but archived anyway so a
    # silent boundary revision cannot make a past run unreconstructable.
    write_history(zcta_bounds, "zcta_bounds", config, stamp=pull_stamp())
