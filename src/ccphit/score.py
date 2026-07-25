"""The mart: join every conformed source onto the ZCTA spine and score it.

Terminal stage of the pipeline. `zcta_scores.geojson` is what gets published to
ArcGIS and backs both the Dashboard and the StoryMap.
"""

import geopandas as gpd
import pandas as pd

from ccphit.config import load_config
from ccphit.io import read_processed, write_geojson, write_processed
from ccphit.weighting import pop_weighted_pct


def assemble_spine(config: dict) -> gpd.GeoDataFrame:
    spine = read_processed(
        "zcta_heat_scores",
        config,
        geo=True,
        require=["zcta", "POP100", "forecast_date", "heat_risk"],
    )
    zcta_svi = read_processed("zcta_svi", config, require=["zcta", "svi"])
    zcta_nearest = read_processed(
        "zcta_nearest_cooling", config, require=["zcta", "dist_m"]
    )

    n = len(spine)

    spine = spine.merge(
        zcta_svi[["zcta", "svi"]],
        on="zcta",
        how="left",
        validate="1:1",
    )
    spine = spine.merge(
        zcta_nearest[["zcta", "dist_m"]],
        on="zcta",
        how="left",
        validate="1:1",
    )

    assert len(spine) == n, f"row count changed: {n} -> {len(spine)}"

    nulls = spine[["heat_risk", "svi", "dist_m"]].isna().sum().to_dict()
    print("nulls:", nulls)

    if nulls["heat_risk"]:
        print("missing heat:", spine.loc[spine["heat_risk"].isna(), "zcta"].tolist())
    if nulls["svi"]:
        print("missing svi:", spine.loc[spine["svi"].isna(), "zcta"].tolist())
    if nulls["dist_m"]:
        print("missing dist:", spine.loc[spine["dist_m"].isna(), "zcta"].tolist())

    return spine


def warn_if_flat(series: pd.Series, name: str) -> None:
    n = series.nunique(dropna=True)
    if n <= 1:
        print(f"WARNING: {name} is flat: {n} unique values")


def score_zctas(spine: gpd.GeoDataFrame, config: dict) -> gpd.GeoDataFrame:
    weights = config["score"]["weights"]
    pop = spine["POP100"]

    for col in ["heat_risk", "svi", "dist_m"]:
        warn_if_flat(spine[col], col)

    spine = spine.copy()
    spine["heat_pct"] = pop_weighted_pct(spine["heat_risk"], pop)
    spine["svi_pct"] = pop_weighted_pct(spine["svi"], pop)
    spine["dist_pct"] = pop_weighted_pct(spine["dist_m"], pop)

    spine["draft_score"] = (
        weights["heat"] * spine["heat_pct"]
        + weights["svi"] * spine["svi_pct"]
        + weights["resource_gap"] * spine["dist_pct"]
    )

    return spine


if __name__ == "__main__":
    config = load_config()
    spine = assemble_spine(config)
    scored = score_zctas(spine, config)

    write_processed(scored, "zcta_scores", config)

    export_cols = [
        "zcta",
        "forecast_date",  # so the published layer states which forecast it reflects
        "heat_risk",
        "svi",
        "dist_m",
        "POP100",
        "heat_pct",
        "svi_pct",
        "dist_pct",
        "draft_score",
        "geometry",
    ]
    write_geojson(scored, "zcta_scores", config, columns=export_cols)

    print(scored["draft_score"].describe())
    top = scored.sort_values("draft_score", ascending=False)[
        ["zcta", "POP100", "draft_score", "svi_pct", "dist_pct"]
    ].head(10)
    print(top)
