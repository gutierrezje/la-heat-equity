"""LA County city and unincorporated-community boundaries (Regional Planning).

Labels, not analysis. Every widget in the Dashboard and StoryMap currently identifies
neighbourhoods by bare 5-digit ZIP, because the Census ZCTA layer carries no place name
— its `NAME` field is literally `"ZCTA5 90813"`.

Chosen over a plain "cities" layer because **roughly a third of LA County is
unincorporated**, and a cities-only layer would leave those ZCTAs unlabelled. This layer
covers incorporated cities and unincorporated communities with no gaps, and
distinguishes them via `JURISDICTION`.

Not counted toward the six-source total: it supplies no measurement, only names.
"""

import geopandas as gpd
import requests

from ccphit.config import load_config
from ccphit.io import pull_stamp, write_history, write_processed

PAGE = 1000


def fetch_place_boundaries(config: dict) -> gpd.GeoDataFrame:
    source = config["sources"]["place_boundaries"]

    params = {
        "where": "1=1",
        "outFields": "CITY_COMM_NAME,JURISDICTION",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "geojson",
    }

    features = []
    offset = 0
    while True:
        response = requests.get(
            source["url"],
            params={**params, "resultOffset": offset, "resultRecordCount": PAGE},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise Exception(data["error"]["message"])
        page = data.get("features", [])
        if not page:
            break
        features.extend(page)
        offset += len(page)

    if not features:
        raise ValueError("place boundaries returned no features")

    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    gdf = gdf.rename(
        columns={"CITY_COMM_NAME": "place_name", "JURISDICTION": "jurisdiction"}
    )
    gdf = gdf[gdf["place_name"].notna()]
    # Source values are upper case; title-case them for display.
    gdf["place_name"] = gdf["place_name"].str.strip().str.title()
    gdf["jurisdiction"] = gdf["jurisdiction"].str.strip().str.title()

    return gdf[["place_name", "jurisdiction", "geometry"]].reset_index(drop=True)


if __name__ == "__main__":
    config = load_config()
    places = fetch_place_boundaries(config)
    write_processed(places, "place_boundaries", config)
    write_history(places, "place_boundaries", config, stamp=pull_stamp())

    print(places["jurisdiction"].value_counts().to_string())
