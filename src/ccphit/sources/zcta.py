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

def attach_heat_scores(la_zctas: gpd.GeoDataFrame, heat_scores: pd.DataFrame) -> gpd.GeoDataFrame:
    la_zctas = la_zctas.copy()
    heat_scores = heat_scores.copy()

    merged = la_zctas.merge(heat_scores, left_on="zcta", right_on="zip", how="left", validate="1:1")
    merged = merged.drop(columns=["zip"])

    matched = merged["heat_risk"].notna().sum()
    print(f"heat match: {matched}/{len(merged)} ZCTAs")
    unmatched = merged.loc[merged["heat_risk"].isna(), "zcta"].tolist()
    print(f"unmatched ZCTAs ({len(unmatched)}):", unmatched)
    
    return merged

if __name__ == "__main__":
    config = load_config()
    county_boundary = fetch_county_boundary(config)
    county_geometry = county_boundary.geometry.union_all()
    minx, miny, maxx, maxy = county_geometry.bounds
    pad = 0.01
    bbox = [minx - pad, miny - pad, maxx + pad, maxy + pad]

    zcta = fetch_zcta(config, bbox)
    la_zctas = zcta[zcta.representative_point().within(county_geometry)].copy()
    write_processed(la_zctas, "zcta_bounds", config)

    heat_scores = pd.read_parquet("data/processed/heat_scores.parquet")
    zcta_heat_scores = attach_heat_scores(la_zctas, heat_scores)
    write_processed(zcta_heat_scores, "zcta_heat_scores", config)