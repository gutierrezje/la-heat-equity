"""Who actually bears the burden, and does "worst place" mean "most people at risk"?

    uv run python -m ccphit.analysis.equity

Three distributional questions the composite score cannot answer on its own:

1. **How concentrated is risk?** If a few ZCTAs carried most of it, targeting would be
   easy. A concentration curve says whether that is true.
2. **Intensity vs burden.** `draft_score` is an intensity (D8) — conditions *per place*.
   Multiplying by population answers a different question, and the two rankings need not
   agree. Whether they do is an empirical matter, not a caveat.
3. **Does the county look different per-place than per-person?** The whole point of D8's
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


def concentration(d: pd.DataFrame, value: str, weight: str) -> tuple[np.ndarray, np.ndarray, float]:
    """Cumulative share of `weight` against cumulative share of total `value*weight`.

    Ordered worst-first, so a steep start means risk is concentrated in few people.
    Returns (x, y, concentration index) where 0 = perfectly even.
    """
    s = d.sort_values(value, ascending=False)
    x = np.concatenate([[0.0], (s[weight].cumsum() / s[weight].sum()).to_numpy()])
    burden = s[value] * s[weight]
    y = np.concatenate([[0.0], (burden.cumsum() / burden.sum()).to_numpy()])
    return x, y, 2 * np.trapezoid(y, x) - 1


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


def figure_concentration(d, x, y, idx):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), width_ratios=[1, 1.1])

    ax = axes[0]
    ax.plot([0, 1], [0, 1], "--", lw=1.2, color=figures.MUTED, label="perfectly even")
    ax.plot(x, y, lw=2.4, color=figures.PALETTE["urban"], label="observed")
    ax.fill_between(x, y, x, alpha=0.12, color=figures.PALETTE["urban"])
    for q in (0.10, 0.25):
        yi = np.interp(q, x, y)
        ax.plot([q, q], [0, yi], lw=0.8, color=figures.MUTED)
        ax.annotate(
            f"worst {q:.0%} of people\nbear {yi:.0%} of risk",
            (q, yi), textcoords="offset points", xytext=(12, -22), fontsize=8,
        )
    ax.set_xlabel("cumulative share of population (worst-scoring first)")
    ax.set_ylabel("cumulative share of total risk")
    ax.set_title("Risk is widespread, not concentrated")
    ax.legend(loc="lower right")
    figures.annotate(ax, f"concentration index = {idx:+.3f}", "upper left")

    ax = axes[1]
    top_burden = set(d.nlargest(10, "burden")["zcta"])
    top_score = set(d.nlargest(10, "draft_score")["zcta"])
    both = top_burden & top_score
    rows = []
    for z in top_score | top_burden:
        r = d[d["zcta"] == z].iloc[0]
        rows.append((r["place_name"], r["draft_score"], r["burden"], z in both))
    rows.sort(key=lambda t: -t[2])
    names = [f"{n}" for n, _, _, _ in rows]
    ypos = np.arange(len(rows))
    ax.barh(
        ypos,
        [b / max(r[2] for r in rows) * 100 for _, _, b, _ in rows],
        color=[figures.PALETTE["urban"] if inb else figures.MUTED for *_, inb in rows],
        height=0.62,
    )
    ax.scatter([s for _, s, _, _ in rows], ypos, color=figures.INK, s=22, zorder=3,
               label="intensity (draft_score)")
    ax.set_yticks(ypos, names, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("burden = score x population (bars, scaled)   ·   score (dots)")
    ax.set_title(f"Intensity and burden disagree\n(only {len(both)} of 10 appear on both lists)")
    ax.legend(loc="lower right")

    fig.suptitle("Where risk is worst is not where most people are at risk", y=1.02)
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
    d["burden"] = d["draft_score"] * d["POP100"]
    print(f"n = {len(d)}  population = {int(d['POP100'].sum()):,}")

    print("\n=== 1. how concentrated is the risk? ===")
    x, y, idx = concentration(d, "draft_score", "POP100")
    for q in (0.05, 0.10, 0.25, 0.50):
        print(f"  worst {q:.0%} of population bears {np.interp(q, x, y):.1%} of total risk")
    print(f"  concentration index: {idx:+.3f}   (0 = spread perfectly evenly)")

    print("\n=== 2. intensity vs burden ===")
    a = set(d.nlargest(10, "burden")["zcta"])
    b = set(d.nlargest(10, "draft_score")["zcta"])
    print(f"  top-10 overlap: {len(a & b)}/10")
    print("  by burden:", ", ".join(d.nlargest(10, "burden")["place_name"]))
    print("  by score :", ", ".join(d.nlargest(10, "draft_score")["place_name"]))

    print("\n=== 3. per-place vs per-person ===")
    cmp = per_place_vs_per_person(d, [*pcts, "draft_score", "dist_m"])
    print(cmp.round(1).to_string(index=False))
    print("\n  (component percentiles are population-weighted by construction, so a")
    print("   per-person mean of exactly 50 is the expected sanity check for D9)")

    if heat_terciles_are_impossible(d["heat_pct"]):
        print("\n  NOTE: heat_pct cannot be cut into terciles — the 33rd and 66th")
        print("  percentiles collide inside one tie group. Saturation (D10) is severe")
        print("  enough to break equal-count binning, so the bivariate map bins heat")
        print("  on its ordinal 0-4 source scale instead.")

    write_processed(
        d[["zcta", "place_name", "POP100", "draft_score", "burden"]], "equity_burden", config
    )
    figures.save(figure_concentration(d, x, y, idx), "equity_concentration")
    figures.save(figure_bivariate(scored.to_crs(CRS_M)), "equity_bivariate")
