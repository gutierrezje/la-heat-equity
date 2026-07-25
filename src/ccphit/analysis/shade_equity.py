"""Test modeled vegetation shade as an intervention-oriented heat-equity layer.

Unlike cooling-center distance, shade is a property of the everyday environment.
This experiment asks whether low 3 p.m. vegetation shade co-occurs with vulnerability
and historical excess-ER heat. It remains observational: correlation does not estimate
the health effect of planting a tree.
"""

import geopandas as gpd
import pandas as pd

from ccphit.analysis import figures
from ccphit.config import CRS_M, load_config
from ccphit.io import read_processed, write_processed

SHADE_COLS = ["building_shade_pct", "vegetation_shade_pct", "total_shade_pct"]


def area_weighted_shade(
    shade: gpd.GeoDataFrame, zctas: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Average ground-area shade percentages across block-group/ZCTA overlaps."""
    blocks = shade[[*SHADE_COLS, "geometry"]].to_crs(CRS_M)
    zones = zctas[["zcta", "geometry"]].to_crs(CRS_M)
    overlap = gpd.overlay(blocks, zones, how="intersection", keep_geom_type=False)
    overlap["_area"] = overlap.geometry.area
    for column in SHADE_COLS:
        overlap[f"_weighted_{column}"] = overlap[column] * overlap["_area"]
    aggregations = {"_area": "sum"}
    aggregations.update({f"_weighted_{column}": "sum" for column in SHADE_COLS})
    grouped = overlap.groupby("zcta", as_index=False).agg(aggregations)
    for column in SHADE_COLS:
        grouped[column] = grouped[f"_weighted_{column}"] / grouped["_area"]
    out = zones.merge(grouped[["zcta", *SHADE_COLS]], on="zcta", how="left")
    return gpd.GeoDataFrame(out, geometry="geometry", crs=CRS_M)


def shade_correlations(d: pd.DataFrame) -> pd.DataFrame:
    """Simple rank relationships; negative means shade is lower where need is higher."""
    measures = {
        "historical_heat_er": "historical heat harm",
        "svi_pct": "social vulnerability",
        "chronic_pct": "chronic disease",
        "heat_risk": "current forecast peak",
    }
    rows = []
    for shade_column in ["vegetation_shade_pct", "total_shade_pct"]:
        for measure, label in measures.items():
            pair = d[[shade_column, measure]].dropna()
            rows.append(
                {
                    "shade_measure": shade_column,
                    "comparison": measure,
                    "label": label,
                    "spearman_rho": pair[shade_column].corr(
                        pair[measure], method="spearman"
                    ),
                    "n": len(pair),
                }
            )
    return pd.DataFrame(rows)


def shade_priority_areas(d: pd.DataFrame) -> pd.DataFrame:
    """Areas simultaneously high in historical harm/SVI and low in vegetation shade."""
    cells = d.dropna(
        subset=[
            "zcta",
            "POP100",
            "svi_pct",
            "historical_heat_er",
            "vegetation_shade_pct",
        ]
    ).copy()
    svi_cut = cells["svi_pct"].quantile(2 / 3)
    historical_band = pd.qcut(
        cells["historical_heat_er"],
        3,
        labels=["lower third", "middle third", "upper third"],
    )
    shade_band = pd.qcut(
        cells["vegetation_shade_pct"],
        3,
        labels=["lower third", "middle third", "upper third"],
    )
    cells["shade_priority"] = (
        (cells["svi_pct"] >= svi_cut)
        & (historical_band == "upper third")
        & (shade_band == "lower third")
    )
    return cells


def figure_shade(d: gpd.GeoDataFrame, correlations: pd.DataFrame):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), width_ratios=[1, 1, 1.25])

    ax = axes[0]
    cells = d.dropna(subset=["svi_pct", "vegetation_shade_pct"]).copy()
    cells["svi_band"] = pd.qcut(
        cells["svi_pct"],
        3,
        labels=["lower third", "middle third", "upper third"],
    )
    groups = [
        cells.loc[cells["svi_band"] == band, "vegetation_shade_pct"].dropna()
        for band in ["lower third", "middle third", "upper third"]
    ]
    ax.boxplot(groups, tick_labels=["lower", "middle", "upper"], showfliers=False)
    ax.set_xlabel("social vulnerability rank")
    ax.set_ylabel("vegetation shade at 3 p.m. (%)")
    ax.set_title("More vulnerable areas\nhave less vegetation shade")

    ax = axes[1]
    vegetation = correlations[
        correlations["shade_measure"] == "vegetation_shade_pct"
    ].sort_values("spearman_rho")
    ax.barh(vegetation["label"], vegetation["spearman_rho"], color="#4f8f62")
    ax.axvline(0, color=figures.INK, lw=0.7)
    ax.set_xlim(-0.8, 0.8)
    ax.set_xlabel("rank relationship with vegetation shade")
    ax.set_title("Shade is scarcest where\nstructural need is highest")
    for y, value in enumerate(vegetation["spearman_rho"]):
        ax.text(value - 0.025, y, f"{value:+.2f}", ha="right", va="center", fontsize=8)

    ax = axes[2]
    priority = d[d["shade_priority"]]
    d.plot(ax=ax, color="#eeeeee", edgecolor="white", linewidth=0.2)
    priority.plot(ax=ax, color="#327a4b", edgecolor="white", linewidth=0.3)
    ax.set_axis_off()
    ax.set_title(
        f"{len(priority)} areas combine high historical harm,\n"
        "high vulnerability, and low vegetation shade"
    )

    fig.suptitle(
        "Shade identifies an intervention geography the facility-distance measure misses",
        y=1.02,
        fontsize=14,
        weight="bold",
    )
    return fig


if __name__ == "__main__":
    import matplotlib.pyplot as plt  # noqa: E402

    figures.setup()
    cfg = load_config()
    shade = read_processed(
        "shade_block_groups",
        cfg,
        geo=True,
        require=["block_group_geoid", *SHADE_COLS],
    )
    zctas = read_processed("zcta_bounds", cfg, geo=True, require=["zcta"])
    validation = read_processed(
        "external_validation",
        cfg,
        require=[
            "zcta",
            "POP100",
            "heat_risk",
            "svi_pct",
            "chronic_pct",
            "historical_heat_er",
        ],
    )

    zcta_shade = area_weighted_shade(shade, zctas)
    result = zcta_shade.merge(validation, on="zcta", how="left", validate="1:1")
    result = shade_priority_areas(result)
    correlations = shade_correlations(result)

    print("\n=== shade relationships ===")
    print(correlations.round(3).to_string(index=False))
    priority = result[result["shade_priority"]]
    print("\n=== intervention screen ===")
    print(f"priority ZCTAs: {len(priority)}")
    print(f"residents: {int(priority['POP100'].sum()):,}")
    print(
        priority.nlargest(12, "POP100")[
            [
                "zcta",
                "place_name",
                "POP100",
                "vegetation_shade_pct",
                "historical_heat_er",
                "svi_pct",
            ]
        ]
        .round(2)
        .to_string(index=False)
    )

    write_processed(
        result.drop(columns="geometry"),
        "shade_equity",
        cfg,
    )
    write_processed(correlations, "shade_correlations", cfg)
    figures.save(figure_shade(result, correlations), "shade_equity")
