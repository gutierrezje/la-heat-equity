"""LA County tract heat score based on historical excess emergency-room visits.

This is an external validation source. It must never become an input to the score it
evaluates, or the validation would be circular.
"""

import pandas as pd
import requests

from ccphit.config import load_config
from ccphit.io import write_processed

FIELDS = [
    "tract",
    "total_pop",
    "heat_tract",
    "heat_cat",
    "svi_score",
    "svi_third",
    "heat_risk",
]
PAGE = 2_000
TIMEOUT = 90


class CountyHeatSchemaError(ValueError):
    """The county response does not match the documented validation layer."""


def normalize_county_heat(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        raise CountyHeatSchemaError("LA County heat outcome layer returned no features")
    df = pd.DataFrame(rows)
    missing = [field for field in FIELDS if field not in df.columns]
    if missing:
        raise CountyHeatSchemaError(f"county heat layer missing fields {missing}")

    out = df[FIELDS].rename(
        columns={
            "tract": "tract_geoid",
            "total_pop": "county_total_pop",
            "heat_tract": "historical_heat_er",
            "heat_cat": "historical_heat_tercile",
            "svi_score": "county_sensitivity",
            "svi_third": "county_sensitivity_tercile",
            "heat_risk": "county_heat_risk",
        }
    )
    geoids = out["tract_geoid"].astype(str).str.strip()
    invalid = ~geoids.str.fullmatch(r"06037\d{6}")
    if invalid.any():
        raise CountyHeatSchemaError(
            f"invalid LA County tract GEOIDs: {sorted(geoids[invalid].unique())[:5]}"
        )
    out["tract_geoid"] = geoids
    if out["tract_geoid"].duplicated().any():
        raise CountyHeatSchemaError("county heat layer contains duplicate tract GEOIDs")

    numeric = [
        "county_total_pop",
        "historical_heat_er",
        "historical_heat_tercile",
        "county_sensitivity",
        "county_sensitivity_tercile",
    ]
    out[numeric] = out[numeric].apply(pd.to_numeric, errors="coerce")
    if out[["historical_heat_er", "historical_heat_tercile"]].isna().any().any():
        raise CountyHeatSchemaError("county heat outcome fields contain missing/non-numeric data")
    invalid_tercile = ~out["historical_heat_tercile"].isin([1, 2, 3])
    if invalid_tercile.any():
        raise CountyHeatSchemaError("historical heat tercile must be 1, 2, or 3")
    return out


def fetch_county_heat(config: dict) -> pd.DataFrame:
    url = config["sources"]["county_heat_outcomes"]["url"]
    base = {
        "where": "1=1",
        "outFields": ",".join(FIELDS),
        "returnGeometry": "false",
        "f": "json",
    }
    rows: list[dict] = []
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
            raise CountyHeatSchemaError(f"county heat service error: {message}")
        page = payload.get("features", [])
        rows.extend(feature["attributes"] for feature in page)
        if not page or not payload.get("exceededTransferLimit", False):
            break
        offset += len(page)
    return normalize_county_heat(rows)


if __name__ == "__main__":
    config = load_config()
    outcomes = fetch_county_heat(config)
    write_processed(outcomes, "county_heat_tracts", config)
    print(outcomes[["historical_heat_er", "historical_heat_tercile"]].describe())
