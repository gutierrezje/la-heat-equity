from pathlib import Path

import geopandas as gpd
import pandas as pd

from ccphit.common import load_config, write_processed

def assemble_spine(config: dict) -> gpd.GeoDataFrame:
    processed = Path(config["paths"]["processed"])

    spine = gpd.read_parquet(processed / "zcta_heat_scores.parquet")
    zcta_svi = gpd.read_parquet(processed / "zcta_svi.parquet")
    zcta_nearest = pd.read_parquet(processed / "zcta_nearest_cooling.parquet")

    n = len(spine)

    # scalar cols only - avoids geometry_x / geometry_y
    spine = spine.merge(
        zcta_svi[["zcta", "svi"]],
        on="zcta",
        how="left",
        validate="1:1"
    )
    spine = spine.merge(
        zcta_nearest[["zcta", "dist_m"]],
        on="zcta",
        how="left",
        validate="1:1"
    )

    assert len(spine) == n, f"row count changed: {n} -> {len(spine)}"

    nulls = spine[["heat_risk", "svi", "dist_m"]].isna().sum().to_dict()

    if nulls["heat_risk"]:
        print("missing heat: ", spine.loc[spine["heat_risk"].isna(), "zcta"].tolist())

    if nulls["svi"]:
        print("missing svi: ", spine.loc[spine["svi"].isna(), "zcta"].tolist())

    if nulls["dist_m"]:
        print("missing dist: ", spine.loc[spine["dist_m"].isna(), "zcta"].tolist())

    return spine

def warn_if_flat(series: pd.Series, name: str) -> None:
    n = series.nunique(dropna=True)
    if n <= 1:
        print(f"WARNING: {name} is flat: {n} unique values")

def pct_rank(series: pd.Series) -> pd.Series:
    return series.rank(pct=True) * 100

def score_zctas(spine: gpd.GeoDataFrame, config: dict) -> gpd.GeoDataFrame:
    weights = config["score"]["weights"]

    for col in ["heat_risk", "svi", "dist_m"]:
        warn_if_flat(spine[col], col)

    spine = spine.copy()
    spine["heat_risk"] = pct_rank(spine["heat_risk"])
    spine["svi"] = pct_rank(spine["svi"])
    spine["dist_m"] = pct_rank(spine["dist_m"])

    spine["draft_score"] = (
        weights["heat"] * spine["heat_risk"] +
        weights["svi"] * spine["svi"] +
        weights["resource_gap"] * spine["dist_m"]
    )

    return spine

if __name__ == "__main__":
    config = load_config()
    spine = assemble_spine(config)
    scored = score_zctas(spine, config)

    write_processed(scored, "zcta_scores", config)

    geosjson_path = Path(config["paths"]["processed"]) / "zcta_scores.geojson"
    export_cols = [
        "zcta", "heat_risk"
    ]
    scored.to_file(geosjson_path, driver="GeoJSON")
    print(f"geojson -> {geosjson_path}")

    print(scored["draft_score"].describe())
    print(scored.sort_values("draft_score", ascending=False)[["zcta", "draft_score"]].head(10))