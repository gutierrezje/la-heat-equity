"""CalEnviroScreen 4.0 (OEHHA/CalEPA) — environmental burden, census tract grain.

Sixth source. Served from CalEPA's ArcGIS org — the same one that hosts CalHeatScore.

**Only the Pollution Burden half is carried, deliberately.** CalEnviroScreen's overall
score (`CIscore`/`CIscoreP`) is Pollution Burden × Population Characteristics, and that
second half is asthma, cardiovascular disease, low birth weight, poverty, education,
linguistic isolation, unemployment, and housing burden — which is precisely what CDC
PLACES and CDC SVI already contribute to the score. Using the combined CES score would
double-count them. `PollutionP` isolates the genuinely additive information. See D15.

Vintage note: CES 4.0 is built on **2010** census tracts, which aligns *better* with the
project's 2010 ZCTA boundaries than SVI 2022's 2020 tracts do. Each tract source is
interpolated onto ZCTAs on its own geometry, so there is no CES-to-SVI key join to
reconcile.
"""

import geopandas as gpd
import requests

from ccphit.config import load_config
from ccphit.io import pull_stamp, write_history, write_processed

PAGE = 1000


def fetch_calenviroscreen(config: dict) -> gpd.GeoDataFrame:
    source = config["sources"]["calenviroscreen"]
    measures = source["measures"]

    params = {
        # `tract` is a Double with the leading zero dropped (6037... not 06037...), so
        # filter on the string companion field instead — LIKE does not work on a Double.
        "where": f"TractTXT LIKE '{source['tract_prefix']}%'",
        "outFields": ",".join(["TractTXT", source["pop_field"], *measures]),
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
        raise ValueError("CalEnviroScreen returned no tracts for the configured prefix")

    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    gdf = gdf.rename(
        columns={"TractTXT": "tract_geoid", source["pop_field"]: "pop", **measures}
    )
    # Restore the leading zero so the id matches the 11-digit FIPS used elsewhere.
    gdf["tract_geoid"] = gdf["tract_geoid"].astype(str).str.zfill(11)

    cols = ["tract_geoid", "pop", *measures.values()]
    gdf = gdf.dropna(subset=["pop"])
    return gdf[[*cols, "geometry"]].reset_index(drop=True)


if __name__ == "__main__":
    config = load_config()
    ces = fetch_calenviroscreen(config)
    write_processed(ces, "ces_tracts", config)

    # Static annual release with no per-record date, so stamp the pull.
    write_history(ces, "ces_tracts", config, stamp=pull_stamp())

    print(ces.drop(columns=["geometry", "tract_geoid"]).describe().round(3).to_string())
