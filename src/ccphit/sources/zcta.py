import requests
import pandas as pd
import geopandas as gpd

from ccphit.common import load_config, write_processed

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

def fetch_zcta(config: dict) -> gpd.GeoDataFrame:
    url = config["sources"]["zcta"]["url"]
    minx, miny, maxx, maxy = config["aoi"]["bbox"]
    params = {
        "geometry": f"{minx},{miny},{maxx},{maxy}",
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
    gdf = gdf[["ZCTA5", "geometry", "POP100"]]
    return gdf.rename(columns={"ZCTA5": "zcta"})

if __name__ == "__main__":
    config = load_config()
    zcta = fetch_zcta(config)
    county_boundary = fetch_county_boundary(config)
    county_geometry = county_boundary.geometry.union_all()
    la_zcta = zcta[zcta.representative_point().within(county_geometry)].copy()
    write_processed(la_zcta, "zcta_bounds", config)