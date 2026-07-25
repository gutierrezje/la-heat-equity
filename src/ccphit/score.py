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
    svi_cols = [
        "svi",
        "svi_socioeconomic",
        "svi_household",
        "svi_minority",
        "svi_housing_transport",
    ]
    places_cols = list(config["sources"]["places"]["measures"].values())

    joins = [
        ("zcta_svi", svi_cols, False),
        ("zcta_nearest_cooling", ["dist_m"], False),
        ("places_zcta", places_cols, False),
    ]

    n = len(spine)
    for name, cols, geo in joins:
        other = read_processed(name, config, geo=geo, require=["zcta", *cols])
        spine = spine.merge(
            other[["zcta", *cols]], on="zcta", how="left", validate="1:1"
        )

    assert len(spine) == n, f"row count changed: {n} -> {len(spine)}"

    tracked = ["heat_risk", *svi_cols, "dist_m", *places_cols]
    nulls = {c: int(spine[c].isna().sum()) for c in tracked if spine[c].isna().any()}
    print("nulls:", nulls if nulls else "none")
    for col in nulls:
        print(f"  missing {col}:", spine.loc[spine[col].isna(), "zcta"].tolist())

    return spine


def warn_if_flat(series: pd.Series, name: str) -> None:
    n = series.nunique(dropna=True)
    if n <= 1:
        print(f"WARNING: {name} is flat: {n} unique values")


def score_zctas(spine: gpd.GeoDataFrame, config: dict) -> gpd.GeoDataFrame:
    """Percentile-rank each component's columns, average within component, weight across.

    Entirely driven by `config.yml`'s `score.components`: adding or reweighting a
    pillar is a config edit, not a code change.
    """
    components = config["score"]["components"]

    total = sum(c["weight"] for c in components.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"score.components weights must sum to 1, got {total}")

    pop = spine["POP100"]
    spine = spine.copy()

    for name, spec in components.items():
        cols = spec["columns"]
        for col in cols:
            warn_if_flat(spine[col], col)

        # Rank each column, then take the unweighted mean of those percentiles.
        # A single-column component reduces to its own percentile.
        ranked = pd.DataFrame(
            {col: pop_weighted_pct(spine[col], pop) for col in cols}
        )
        spine[f"{name}_pct"] = ranked.mean(axis=1)

    spine["draft_score"] = sum(
        spec["weight"] * spine[f"{name}_pct"] for name, spec in components.items()
    )

    return spine


if __name__ == "__main__":
    config = load_config()
    spine = assemble_spine(config)
    scored = score_zctas(spine, config)

    write_processed(scored, "zcta_scores", config)

    component_pcts = [f"{name}_pct" for name in config["score"]["components"]]
    places_cols = list(config["sources"]["places"]["measures"].values())
    export_cols = [
        "zcta",
        "forecast_date",  # so the published layer states which forecast it reflects
        "POP100",
        # raw inputs, for popups
        "heat_risk",
        "svi",
        "dist_m",
        *places_cols,
        # SVI sub-themes, for the dashboard's domain breakdown chart
        "svi_socioeconomic",
        "svi_household",
        "svi_minority",
        "svi_housing_transport",
        # component percentiles + composite
        *component_pcts,
        "draft_score",
        "geometry",
    ]
    write_geojson(scored, "zcta_scores", config, columns=export_cols)

    print(scored["draft_score"].describe())
    top = scored.sort_values("draft_score", ascending=False)[
        ["zcta", "POP100", "draft_score", *component_pcts]
    ].head(10)
    print(top)
