"""CalHeatScore — per-ZIP seven-day heat-health risk forecast.

The service publishes only the current window. All seven daily scores are retained
before deriving summaries so future analyses can compare peak and duration without
pretending that the ordinal scores are physical exposure units.
"""

import pandas as pd
import requests

from ccphit.config import load_config
from ccphit.io import write_history, write_processed

DAY_FIELDS = [f"CHS_Day_{i}" for i in range(7)]
DAY_COLS = [f"heat_day_{i}" for i in range(7)]
SCORE_MIN, SCORE_MAX = 0, 4
TIMEOUT = 60
PAGE = 2_000


class HeatScoreSchemaError(ValueError):
    """The service response is not the seven-day 0–4 forecast the pipeline expects."""


def normalize_heat_scores(rows: list[dict], method_version: str) -> pd.DataFrame:
    """Validate and reshape raw service attributes without performing network I/O."""
    if not rows:
        raise HeatScoreSchemaError("CalHeatScore returned no features")
    if not method_version:
        raise HeatScoreSchemaError("CalHeatScore method version is empty")

    df = pd.DataFrame(rows)
    required = ["ZIP_CODE", "DATE", *DAY_FIELDS]
    missing = [field for field in required if field not in df.columns]
    if missing:
        raise HeatScoreSchemaError(
            f"missing required CalHeatScore fields {missing}; got {sorted(df.columns)}"
        )

    days = df[DAY_FIELDS].apply(pd.to_numeric, errors="coerce")
    if days.isna().any().any():
        bad = days.columns[days.isna().any()].tolist()
        raise HeatScoreSchemaError(f"non-numeric daily scores in {bad}")
    fractional = (days % 1) != 0
    if fractional.any().any():
        found = sorted(set(days.to_numpy()[fractional.to_numpy()].tolist()))
        raise HeatScoreSchemaError(f"daily scores must be integers: {found}")
    days = days.astype(int)

    out_of_range = (days < SCORE_MIN) | (days > SCORE_MAX)
    if out_of_range.any().any():
        found = sorted(set(days.to_numpy()[out_of_range.to_numpy()].tolist()))
        raise HeatScoreSchemaError(
            f"daily scores outside {SCORE_MIN}-{SCORE_MAX}: {found}"
        )

    zips = df["ZIP_CODE"].astype(str).str.strip()
    invalid_zip = ~zips.str.fullmatch(r"\d{1,5}")
    if invalid_zip.any():
        raise HeatScoreSchemaError(
            f"invalid ZIP_CODE values: {sorted(zips[invalid_zip].unique().tolist())}"
        )
    dates = df["DATE"].astype(str).str.strip()
    if dates.eq("").any():
        raise HeatScoreSchemaError("empty DATE values")

    days.columns = DAY_COLS
    out = pd.DataFrame(
        {
            "zip": zips.str.zfill(5),
            "forecast_date": dates,
        }
    ).join(days)
    if out["zip"].duplicated().any():
        duplicates = sorted(out.loc[out["zip"].duplicated(False), "zip"].unique())
        raise HeatScoreSchemaError(f"duplicate ZIP forecasts: {duplicates}")

    out["heat_risk"] = days.max(axis=1)
    out["heat_days_ge_3"] = (days >= 3).sum(axis=1)
    # An ordinal severity-days index, not a physical dose or attributable burden.
    out["heat_score_days"] = days.sum(axis=1)
    out["calheatscore_method_version"] = method_version
    return out


def fetch_heat_scores(config: dict) -> pd.DataFrame:
    """Fetch every service page and return a validated, normalized forecast."""
    source = config["sources"]["calheatscore"]
    params = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "false",
        "f": "json",
    }

    rows: list[dict] = []
    offset = 0
    while True:
        response = requests.get(
            source["url"],
            params={**params, "resultOffset": offset, "resultRecordCount": PAGE},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            message = data["error"].get("message", str(data["error"]))
            raise HeatScoreSchemaError(f"CalHeatScore service error: {message}")
        page = data.get("features", [])
        if not isinstance(page, list):
            raise HeatScoreSchemaError("CalHeatScore features is not a list")
        rows.extend(feature["attributes"] for feature in page)
        if not page or not data.get("exceededTransferLimit", False):
            break
        offset += len(page)

    return normalize_heat_scores(rows, source["method_version"])


if __name__ == "__main__":
    config = load_config()
    heat_scores = fetch_heat_scores(config)
    write_processed(heat_scores, "heat_scores", config)

    # Earlier archives kept only the maximum and cannot be repaired. From this pull
    # onward, retain the source daily series before it disappears from the live service.
    write_history(
        heat_scores,
        "heat_scores",
        config,
        stamp=heat_scores["forecast_date"].max(),
    )
