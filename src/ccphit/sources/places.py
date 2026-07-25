"""CDC PLACES 2024 release — model-based chronic disease prevalence, ZCTA grain.

The chronic-disease pillar the proposal's score formula names. Unlike SVI this needs
**no crosswalk**: CDC publishes ZCTA-level estimates directly, so it joins on `zcta`
like CalHeatScore does.

Values are modeled crude prevalence (percent of adults) derived from BRFSS 2022 +
ACS 2018-2022 — not direct measurements for the ZCTA. Coverage is 285 of 294 LA
County ZCTAs; the 9 misses total 111 residents, so population coverage is ~100%.
"""

import pandas as pd
import requests

from ccphit.config import load_config
from ccphit.io import pull_stamp, write_history, write_processed


def fetch_places(config: dict) -> pd.DataFrame:
    source = config["sources"]["places"]
    measures = source["measures"]
    minx, miny, maxx, maxy = config["aoi"]["bbox"]

    params = {
        "$select": ",".join(["zcta5", *measures]),
        # Socrata within_box takes the NW corner then the SE corner, as lat/lon pairs.
        # PLACES carries no state or county field, so the AOI bbox is the only
        # server-side filter available; the ZCTA spine join defines real scope (D2).
        "$where": f"within_box(geolocation, {maxy}, {minx}, {miny}, {maxx})",
        "$limit": 5000,
    }
    response = requests.get(source["url"], params=params, timeout=60)
    response.raise_for_status()

    df = pd.DataFrame(response.json())
    if df.empty:
        raise ValueError("PLACES returned no rows for the AOI bbox")

    df = df.rename(columns={"zcta5": "zcta", **measures})
    df["zcta"] = df["zcta"].astype(str).str.zfill(5)
    for col in measures.values():
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df[["zcta", *measures.values()]]


if __name__ == "__main__":
    config = load_config()
    places = fetch_places(config)
    write_processed(places, "places_zcta", config)

    # Annual release carrying no per-record date, so stamp the pull.
    write_history(places, "places_zcta", config, stamp=pull_stamp())

    print(places.drop(columns="zcta").describe().round(1).to_string())
