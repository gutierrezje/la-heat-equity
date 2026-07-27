"""Build the stable ArcGIS layer consumed by the StoryMap and Dashboard.

The product has two views over one ZCTA layer:

* short-term response snapshot: forecast severity + social vulnerability;
* long-term investment: historical heat harm + vulnerability + low shade.

Category fields are calculated here rather than in ArcGIS expressions so every
consumer uses the same transparent rules.
"""

import geopandas as gpd
import pandas as pd

from ccphit.analysis.shade_equity import SHADE_COLS, area_weighted_shade
from ccphit.analysis.validation import build_validation
from ccphit.config import load_config
from ccphit.io import read_processed, write_geojson, write_processed


def tercile(series: pd.Series, reverse: bool = False) -> pd.Series:
    """Return stable 1–3 place-based terciles; 3 always means greater concern."""
    valid = series.dropna()
    out = pd.Series(pd.NA, index=series.index, dtype="Int64")
    if len(valid) < 3:
        return out
    ranked = valid.rank(method="average")
    values = pd.qcut(ranked, 3, labels=[1, 2, 3]).astype("Int64")
    if reverse:
        values = 4 - values
    out.loc[valid.index] = values
    return out


def format_product(layer: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add ArcGIS-safe categories and flags to an already joined ZCTA layer."""
    out = layer.copy()
    out["response_index"] = (
        0.50 * out["heat_pct"] + 0.25 * out["svi_pct"] + 0.25 * out["chronic_pct"]
    )
    out["svi_tercile"] = tercile(out["svi_pct"])
    out["historical_heat_tercile"] = tercile(out["historical_heat_er"])
    out["low_shade_tercile"] = tercile(out["vegetation_shade_pct"], reverse=True)

    current = (
        out["heat_risk"].eq(4) & out["svi_tercile"].eq(3)
    ).fillna(False)
    investment = (
        out["historical_heat_tercile"].eq(3)
        & out["svi_tercile"].eq(3)
        & out["low_shade_tercile"].eq(3)
    ).fillna(False)
    out["response_priority"] = current.astype("int8")
    out["investment_priority"] = investment.astype("int8")

    out["response_category"] = "Other short-term snapshot conditions"
    out.loc[
        out["heat_risk"].eq(4) & ~out["svi_tercile"].eq(3),
        "response_category",
    ] = "Extreme heat"
    out.loc[
        out["heat_risk"].lt(4) & out["svi_tercile"].eq(3),
        "response_category",
    ] = "High vulnerability"
    out.loc[current, "response_category"] = "Extreme heat + high vulnerability"

    out["investment_category"] = "Other structural conditions"
    out.loc[
        out["historical_heat_tercile"].eq(3) & out["svi_tercile"].eq(3),
        "investment_category",
    ] = "High historical harm + high vulnerability"
    out.loc[
        investment,
        "investment_category",
    ] = "High harm + high vulnerability + low shade"
    return out


def build_product(config: dict) -> gpd.GeoDataFrame:
    validation = build_validation(config)
    shade = read_processed(
        "shade_block_groups", config, geo=True, require=["block_group_geoid", *SHADE_COLS]
    )
    zctas = read_processed("zcta_bounds", config, geo=True, require=["zcta"])
    zcta_shade = area_weighted_shade(shade, zctas).drop(columns="geometry")
    joined = validation.merge(zcta_shade, on="zcta", how="left", validate="1:1")
    return format_product(gpd.GeoDataFrame(joined, geometry="geometry", crs=validation.crs))


def export_columns(config: dict, layer: gpd.GeoDataFrame) -> list[str]:
    """The deliberate public schema; analytical scratch columns stay in parquet."""
    places = list(config["sources"]["places"]["measures"].values())
    daily = sorted(c for c in layer if c.startswith("heat_day_"))
    return [
        "zcta", "place_name", "jurisdiction", "places_touched", "forecast_date",
        "POP100", "heat_risk", *daily, "heat_days_ge_3", "heat_score_days",
        "calheatscore_method_version",
        "svi", "svi_socioeconomic", "svi_household", "svi_minority",
        "svi_housing_transport", *places, "chronic_top",
        "historical_heat_er", *SHADE_COLS, "dist_m",
        "heat_pct", "svi_pct", "chronic_pct", "resource_gap_pct",
        "response_index", "draft_score", "svi_tercile",
        "historical_heat_tercile", "low_shade_tercile",
        "response_priority", "response_category",
        "investment_priority", "investment_category", "geometry",
    ]


if __name__ == "__main__":
    cfg = load_config()
    product = build_product(cfg)
    write_processed(product, "zcta_product", cfg)
    write_geojson(product, "zcta_scores", cfg, columns=export_columns(cfg, product))
    for field in ("response_priority", "investment_priority"):
        selected = product[field].eq(1)
        print(
            f"{field}: {int(selected.sum())} ZCTAs; "
            f"{int(product.loc[selected, 'POP100'].sum()):,} residents"
        )
