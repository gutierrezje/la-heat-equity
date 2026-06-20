# fetch cooling centers from ArcGIS

import os
import requests
import geopandas as gpd

from ccphit.common import load_config

def fetch_cooling_centers(config: dict) -> gpd.GeoDataFrame:
    url = config["sources"]["cooling"]["url"]
    # Fetch: GET ?where=1=1&outFields=*&f=geojson — paginate with resultOffset if needed
    # (most cooling-center layers are <500 features; skip pagination until it fails)
    offset = 0
    all_features = []

    while True:
        response = requests.get(url, params={"where": "1=1", "outFields": "*", "f": "geojson", "resultOffset": offset})
        response.raise_for_status()
        data = response.json()
        features = data.get("features", [])
        if len(features) == 0:
            break
        all_features.extend(features)
        offset += len(data["features"])

    return gpd.GeoDataFrame.from_features(all_features).set_crs(epsg=4326)

if __name__ == "__main__":
    config = load_config()
    cooling_centers = fetch_cooling_centers(config)
    print(cooling_centers.head())