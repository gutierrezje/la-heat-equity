"""How many residents live in explicitly defined heat × vulnerability categories?

    uv run python -m ccphit.analysis.equity

Two distributional questions the composite score cannot answer on its own:

1. **How many people live in each declared priority category?** This sums Census
   population after applying visible heat and vulnerability rules; it does not convert an
   ordinal index into cases or "burden."
2. **Does the county look different per-place than per-person?** The whole point of D8's
   population weighting, checked distributionally.

Also draws the bivariate heat x vulnerability map the proposal asks for, which shows two
dimensions at once instead of collapsing them into a weighted sum.
"""

import numpy as np
import pandas as pd

from ccphit.analysis import figures
from ccphit.config import CRS_M, load_config
from ccphit.io import read_processed, write_processed

# 3x3 bivariate scheme: rows = vulnerability (low->high), cols = heat (low->high).
# Blue-ish = vulnerable but cool, orange-ish = hot but not vulnerable, dark = both.
BIVARIATE = [
    ["#e8e8e8", "#e4acac", "#c85a5a"],
    ["#b0d5df", "#ad9ea5", "#985356"],
    ["#64acbe", "#627f8c", "#574249"],
]


HEAT_BANDS = ["lower (0–2)", "high (3)", "extreme (4)"]
SVI_BANDS = ["lower third", "middle third", "upper third"]


def classify_priority_cells(d: pd.DataFrame) -> pd.DataFrame:
    """Assign transparent heat × vulnerability categories used by map and totals."""
    out = d.dropna(subset=["heat_risk", "svi_pct", "POP100"]).copy()
    out["heat_band"] = pd.Categorical(
        np.select(
            [out["heat_risk"] <= 2, out["heat_risk"] == 3],
            HEAT_BANDS[:2],
            default=HEAT_BANDS[2],
        ),
        categories=HEAT_BANDS,
        ordered=True,
    )
    out["svi_band"] = pd.Categorical(
        pd.qcut(out["svi_pct"], 3, labels=SVI_BANDS),
        categories=SVI_BANDS,
        ordered=True,
    )
    return out


def priority_population(d: pd.DataFrame) -> pd.DataFrame:
    """Count areas and residents in each declared cell; every row contributes once."""
    cells = classify_priority_cells(d)
    summary = (
        cells.groupby(["svi_band", "heat_band"], observed=False)
        .agg(zctas=("zcta", "size"), population=("POP100", "sum"))
        .reset_index()
    )
    summary["population_share"] = summary["population"] / summary["population"].sum()
    return summary


def per_place_vs_per_person(d: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    rows = []
    for c in cols:
        rows.append(
            {
                "variable": c,
                "per_place": d[c].mean(),
                "per_person": np.average(d[c], weights=d["POP100"]),
            }
        )
    out = pd.DataFrame(rows)
    out["difference"] = out["per_person"] - out["per_place"]
    return out


def figure_priority_population(summary: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    grid = summary.pivot(index="svi_band", columns="heat_band", values="population")
    values = grid.to_numpy() / 1e6
    im = ax.imshow(values, cmap="YlOrRd", aspect="auto")
    for row in range(values.shape[0]):
        for col in range(values.shape[1]):
            cell = summary[
                (summary["svi_band"] == grid.index[row])
                & (summary["heat_band"] == grid.columns[col])
            ].iloc[0]
            ax.text(
                col,
                row,
                f"{values[row, col]:.2f}M people\n{int(cell['zctas'])} areas",
                ha="center",
                va="center",
                color="white" if values[row, col] > values.max() * 0.55 else figures.INK,
                weight="bold",
            )
    ax.set_xticks(range(len(grid.columns)), grid.columns)
    ax.set_yticks(range(len(grid.index)), grid.index)
    ax.set_xlabel("seven-day forecast snapshot peak CalHeatScore")
    ax.set_ylabel("social vulnerability rank")
    ax.set_title(
        "Residents of explicitly defined heat × vulnerability categories\n"
        "Population in a flagged area—not an estimate of illness or people harmed"
    )
    fig.colorbar(im, ax=ax, label="millions of residents")
    return fig


def heat_terciles_are_impossible(heat_pct: pd.Series) -> bool:
    """True when `heat_pct` has too few distinct values to cut into three groups.

    On a saturated forecast most ZCTAs share the top `heat_risk` and therefore share one
    percentile, so the 33rd and 66th percentiles collide (D10). Worth detecting explicitly
    rather than catching a bin-edge error.
    """
    edges = heat_pct.quantile([0, 1 / 3, 2 / 3, 1]).to_numpy()
    return len(np.unique(edges)) < 4


def figure_bivariate(gdf):
    """Heat x vulnerability, without collapsing them into a weighted sum."""
    d = gdf.dropna(subset=["heat_pct", "svi_pct"]).copy()

    # Heat is binned on its ordinal source scale, not by terciles: CalHeatScore is 0-4 and
    # saturates, so equal-count heat bins do not exist on a hot forecast (D10).
    d["hx"] = np.select(
        [d["heat_risk"] <= 2, d["heat_risk"] == 3], [0, 1], default=2
    ).astype(int)
    d["vy"] = pd.qcut(d["svi_pct"], 3, labels=[0, 1, 2]).astype(int)
    d["color"] = [BIVARIATE[v][h] for v, h in zip(d["vy"], d["hx"])]

    fig = plt.figure(figsize=(9.6, 8.8))
    ax = fig.add_axes([0.02, 0.06, 0.96, 0.86])
    d.plot(ax=ax, color=d["color"], edgecolor="white", linewidth=0.25)
    gdf[gdf["heat_pct"].isna() | gdf["svi_pct"].isna()].plot(
        ax=ax, color="#f7f7f7", edgecolor="white", linewidth=0.25
    )
    ax.set_axis_off()
    counts = d.groupby(["vy", "hx"]).size()
    both_high = int(counts.get((2, 2), 0))
    ax.set_title(
        "Heat and vulnerability, shown separately\n"
        "dark = both high · blue = vulnerable but cooler · red = hot but less vulnerable\n"
        f"{both_high} ZCTAs are in the top third for vulnerability AND at extreme heat"
    )

    leg = fig.add_axes([0.06, 0.10, 0.16, 0.16])
    for v in range(3):
        for h in range(3):
            leg.add_patch(plt.Rectangle((h, v), 1, 1, color=BIVARIATE[v][h]))
    leg.set_xlim(0, 3)
    leg.set_ylim(0, 3)
    leg.set_xticks([])
    leg.set_yticks([])
    leg.set_xlabel("heat risk (≤2 / 3 / 4) →", fontsize=8)
    leg.set_ylabel("vulnerability tercile →", fontsize=8)
    for s in leg.spines.values():
        s.set_visible(False)
    return fig


if __name__ == "__main__":
    import matplotlib.pyplot as plt  # noqa: E402

    figures.setup()
    config = load_config()
    pcts = [f"{n}_pct" for n in config["score"]["components"]]

    scored = read_processed("zcta_scores", config, geo=True, require=["zcta", "draft_score"])
    d = scored.dropna(subset=["draft_score"]).copy()
    d = d[d["POP100"] > 0].reset_index(drop=True)
    print(f"n = {len(d)}  population = {int(d['POP100'].sum()):,}")

    print("\n=== 1. how many people live in each declared priority category? ===")
    population = priority_population(d)
    print(population.to_string(index=False))

    print("\n=== 2. per-place vs per-person ===")
    cmp = per_place_vs_per_person(d, [*pcts, "draft_score", "dist_m"])
    print(cmp.round(1).to_string(index=False))
    print("\n  (component percentiles are population-weighted by construction, so a")
    print("   per-person mean of exactly 50 is the expected sanity check for D9)")

    if heat_terciles_are_impossible(d["heat_pct"]):
        print("\n  NOTE: heat_pct cannot be cut into terciles — the 33rd and 66th")
        print("  percentiles collide inside one tie group. Saturation (D10) is severe")
        print("  enough to break equal-count binning, so the bivariate map bins heat")
        print("  on its ordinal 0-4 source scale instead.")

    write_processed(population, "equity_priority_population", config)
    figures.save(
        figure_priority_population(population),
        "equity_priority_population",
    )
    figures.save(figure_bivariate(scored.to_crs(CRS_M)), "equity_bivariate")
