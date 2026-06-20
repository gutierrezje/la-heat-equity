# fetch cooling centers from ArcGIS

import os
import requests
import geopandas as gpd

from ccphit.common import clip_to_aoi, write_processed, load_config

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

    gdf = gpd.GeoDataFrame.from_features(all_features)
    gdf.set_crs(epsg=4326, inplace=True)
    gdf = clip_to_aoi(gdf, config["aoi"])
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    gdf = gdf[["Site_Name", "Address", "Days_Hours_of_Operation", "geometry"]]
    gdf.columns = ["site_name", "address", "days_hours_of_operation", "geometry"]
    
    return gdf

if __name__ == "__main__":
    config = load_config()
    cooling_centers = fetch_cooling_centers(config)
    write_processed(cooling_centers, "cooling", config)