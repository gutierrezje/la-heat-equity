"""Is heat-equity risk spatially clustered, and where are the significant hot spots?

    uv run python -m ccphit.analysis.spatial

A choropleth always *looks* patterned — the eye invents clusters. Global Moran's I tests
whether the pattern is more clustered than chance, and Local Moran (LISA) says which
individual ZCTAs belong to a statistically significant cluster.

Spatial **outliers** are something a ranked list cannot show: an area with a low index
surrounded by high-index neighbors, or the reverse. They are descriptive flags, not proof
that a municipal boundary caused the difference.

Weights note: LA County has one island (Santa Catalina, 90704) with no queen contiguity.
It is reported separately rather than being assigned invented cross-water neighbors.
Local results use false-discovery-rate control because every mainland area is tested.
"""

import numpy as np
import pandas as pd
from esda.moran import Moran, Moran_Local
from libpysal.weights import Queen

from ccphit.analysis import figures
from ccphit.config import CRS_M, load_config
from ccphit.io import read_processed, write_processed

PERMUTATIONS = 999
SEED = 7
ALPHA = 0.05
ISLAND_LABEL = "not evaluated (island)"

QUADRANT = {1: "HH hot spot", 2: "LH outlier", 3: "LL cold spot", 4: "HL outlier"}
LISA_COLORS = {
    "HH hot spot": "#c1272d",
    "LL cold spot": "#4575b4",
    "LH outlier": "#92c5de",
    "HL outlier": "#f4a582",
    "not significant": "#e8e8e8",
    ISLAND_LABEL: "#ffffff",
}


def spatial_sample(gdf):
    """Keep land-contiguous areas together and report islands separately.

    Switching the entire county to K-nearest neighbors because Catalina has no land
    neighbor changes every mainland relationship. The estimand here is contiguous
    clustering, so an island is an explicit non-estimable case rather than a reason to
    replace the graph.
    """
    queen = Queen.from_dataframe(gdf, use_index=False, silence_warnings=True)
    islands = gdf.iloc[queen.islands].copy()
    mainland = gdf.drop(index=queen.islands).reset_index(drop=True)
    w = Queen.from_dataframe(mainland, use_index=False, silence_warnings=True)
    if w.islands:
        raise ValueError(f"mainland queen graph still contains islands: {w.islands}")
    w.transform = "r"
    note = (
        f"Queen contiguity; {len(islands)} island(s) reported separately "
        "without invented cross-water neighbors"
    )
    return mainland, islands, w, note


def benjamini_hochberg(p_values) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values for false-discovery-rate control."""
    p = np.asarray(p_values, dtype=float)
    if p.ndim != 1 or np.isnan(p).any() or ((p < 0) | (p > 1)).any():
        raise ValueError("p-values must be a one-dimensional array in [0, 1]")
    n = len(p)
    if n == 0:
        return p.copy()
    order = np.argsort(p)
    ranked = p[order]
    adjusted = ranked * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1].clip(0, 1)
    out = np.empty_like(adjusted)
    out[order] = adjusted
    return out


def global_moran(gdf, cols, w):
    rows = []
    for col in cols:
        mi = Moran(gdf[col].to_numpy(), w, permutations=PERMUTATIONS)
        rows.append(
            {"variable": col, "morans_I": mi.I, "z": mi.z_sim, "p": mi.p_sim,
             "expected_I": mi.EI}
        )
    return pd.DataFrame(rows)


def local_moran(gdf, col, w):
    lm = Moran_Local(gdf[col].to_numpy(), w, permutations=PERMUTATIONS, seed=SEED)
    out = gdf[["zcta", "place_name", "POP100", col]].copy()
    out["lisa_p"] = lm.p_sim
    out["lisa_q"] = benjamini_hochberg(lm.p_sim)
    out["lisa"] = [
        QUADRANT[quadrant] if q_value < ALPHA else "not significant"
        for quadrant, q_value in zip(lm.q, out["lisa_q"])
    ]
    out["spatial_lag"] = lm.w.sparse @ (
        (gdf[col] - gdf[col].mean()) / gdf[col].std()
    ).to_numpy()
    out["z_score"] = ((gdf[col] - gdf[col].mean()) / gdf[col].std()).to_numpy()
    return out


def figure_moran_scatter(lisa, col):
    fig, ax = plt.subplots(figsize=(6.2, 5.8))
    for label, color in LISA_COLORS.items():
        sub = lisa[lisa["lisa"] == label]
        ax.scatter(
            sub["z_score"], sub["spatial_lag"], s=26, color=color, alpha=0.85,
            label=f"{label} ({len(sub)})", edgecolor="white", linewidth=0.4,
            zorder=2 if label != "not significant" else 1,
        )
    lim = max(abs(lisa["z_score"]).max(), abs(lisa["spatial_lag"]).max()) * 1.1
    ax.axhline(0, lw=0.7, color=figures.MUTED)
    ax.axvline(0, lw=0.7, color=figures.MUTED)
    b = np.polyfit(lisa["z_score"], lisa["spatial_lag"], 1)
    xs = np.array([-lim, lim])
    ax.plot(xs, np.polyval(b, xs), "--", lw=1.2, color=figures.INK)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_xlabel(f"{col} (standardised)")
    ax.set_ylabel("mean of neighbours (spatial lag)")
    ax.set_title("Moran scatterplot: risk resembles its neighbours")
    ax.legend(loc="upper left")
    figures.annotate(ax, f"slope = Moran's I = {b[0]:.2f}", "lower right")
    return fig


def figure_lisa_map(gdf, lisa, note):
    merged = gdf.merge(lisa[["zcta", "lisa"]], on="zcta", how="left")
    fig, ax = plt.subplots(figsize=(8.6, 8.6))
    for label, color in LISA_COLORS.items():
        sub = merged[merged["lisa"] == label]
        if len(sub):
            sub.plot(ax=ax, color=color, edgecolor="white", linewidth=0.25,
                     label=f"{label} ({len(sub)})")
    ax.set_axis_off()
    ax.set_title(
        "Clusters of heat-equity index values\n"
        f"Local Moran, {PERMUTATIONS} permutations, FDR q < {ALPHA}",
    )
    ax.legend(loc="lower left", title=None)
    fig.text(0.5, 0.055, f"weights: {note}", ha="center", fontsize=7.5,
             color=figures.MUTED, style="italic")

    for _, r in merged[merged["lisa"].isin(["LH outlier", "HL outlier"])].iterrows():
        c = r.geometry.representative_point()
        ax.annotate(
            r["place_name"], (c.x, c.y), fontsize=7.5, weight="bold",
            ha="center", color=figures.INK,
        )
    return fig


if __name__ == "__main__":
    import matplotlib.pyplot as plt  # noqa: E402

    figures.setup()
    config = load_config()
    pcts = [f"{n}_pct" for n in config["score"]["components"]]

    scored = read_processed("zcta_scores", config, geo=True, require=["zcta", "draft_score"])
    gdf = scored.dropna(subset=["draft_score", *pcts]).to_crs(CRS_M).reset_index(drop=True)
    print(f"n = {len(gdf)} scored ZCTAs")

    mainland, islands, w, note = spatial_sample(gdf)
    print(f"weights: {note}")

    print("\n=== global Moran's I ===")
    gm = global_moran(mainland, ["draft_score", *pcts], w)
    print(gm.round(4).to_string(index=False))
    print("\n(I = 0 would be spatial randomness; p is the permutation pseudo p-value)")

    print("\n=== local Moran (LISA) on draft_score ===")
    lisa = local_moran(mainland, "draft_score", w)
    if len(islands):
        island_rows = islands[["zcta", "place_name", "POP100", "draft_score"]].copy()
        island_rows["lisa_p"] = np.nan
        island_rows["lisa_q"] = np.nan
        island_rows["lisa"] = ISLAND_LABEL
        island_rows["spatial_lag"] = np.nan
        island_rows["z_score"] = np.nan
        lisa = pd.concat([lisa, island_rows], ignore_index=True)
    print(lisa["lisa"].value_counts().to_string())
    write_processed(lisa, "spatial_lisa", config)

    print("\n--- spatial outliers: where the index changes sharply ---")
    for kind in ["LH outlier", "HL outlier"]:
        sub = lisa[lisa["lisa"] == kind].nlargest(5, "POP100")
        for r in sub.itertuples():
            print(f"  {kind}: {r.place_name} ({r.zcta}) pop={int(r.POP100):>6} "
                  f"score={r.draft_score:.1f}")

    print("\n--- largest hot spots by population ---")
    for r in lisa[lisa["lisa"] == "HH hot spot"].nlargest(6, "POP100").itertuples():
        print(f"  {r.place_name} ({r.zcta}) pop={int(r.POP100):>6} score={r.draft_score:.1f}")

    hh = lisa[lisa["lisa"] == "HH hot spot"]
    print(f"\nhot-spot ZCTAs hold {hh['POP100'].sum() / lisa['POP100'].sum():.0%} "
          "of the scored population")

    figures.save(
        figure_moran_scatter(lisa[lisa["lisa"] != ISLAND_LABEL], "draft_score"),
        "spatial_moran_scatter",
    )
    figures.save(figure_lisa_map(gdf, lisa, note), "spatial_lisa_map")
