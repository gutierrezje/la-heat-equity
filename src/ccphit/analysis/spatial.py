"""Is heat-equity risk spatially clustered, and where are the significant hot spots?

    uv run python -m ccphit.analysis.spatial

A choropleth always *looks* patterned — the eye invents clusters. Global Moran's I tests
whether the pattern is more clustered than chance, and Local Moran (LISA) says which
individual ZCTAs belong to a statistically significant cluster.

The spatial **outliers** are the finding that a ranked list cannot produce: a low-risk
ZCTA surrounded by high-risk ones is a place where the burden changes sharply over a short
distance, usually at a municipal boundary.

Weights note: LA County has one island (Santa Catalina, 90704) with no queen contiguity,
which would be silently dropped from a contiguity matrix. K-nearest-neighbours keeps every
ZCTA in the analysis at the cost of giving Catalina six mainland "neighbours" — so its
result is reported but flagged rather than trusted.
"""

import numpy as np
from esda.moran import Moran, Moran_Local
from libpysal.weights import KNN, Queen

from ccphit.analysis import figures
from ccphit.config import CRS_M, load_config
from ccphit.io import read_processed, write_processed

K_NEIGHBOURS = 6
PERMUTATIONS = 999
SEED = 7
ALPHA = 0.05

QUADRANT = {1: "HH hot spot", 2: "LH outlier", 3: "LL cold spot", 4: "HL outlier"}
LISA_COLORS = {
    "HH hot spot": "#c1272d",
    "LL cold spot": "#4575b4",
    "LH outlier": "#92c5de",
    "HL outlier": "#f4a582",
    "not significant": "#e8e8e8",
}


def build_weights(gdf):
    """Queen contiguity where possible, KNN when islands would be dropped."""
    queen = Queen.from_dataframe(gdf, use_index=False, silence_warnings=True)
    if queen.islands:
        w = KNN.from_dataframe(gdf, k=K_NEIGHBOURS)
        note = (
            f"KNN(k={K_NEIGHBOURS}) — {len(queen.islands)} island(s) have no queen "
            "contiguity and would otherwise be dropped"
        )
    else:
        w = queen
        note = "Queen contiguity"
    w.transform = "r"
    return w, note


def global_moran(gdf, cols, w):
    rows = []
    for col in cols:
        mi = Moran(gdf[col].to_numpy(), w, permutations=PERMUTATIONS)
        rows.append(
            {"variable": col, "morans_I": mi.I, "z": mi.z_sim, "p": mi.p_sim,
             "expected_I": mi.EI}
        )
    import pandas as pd

    return pd.DataFrame(rows)


def local_moran(gdf, col, w):
    lm = Moran_Local(gdf[col].to_numpy(), w, permutations=PERMUTATIONS, seed=SEED)
    out = gdf[["zcta", "place_name", "POP100", col]].copy()
    out["lisa"] = [
        QUADRANT[q] if p < ALPHA else "not significant" for q, p in zip(lm.q, lm.p_sim)
    ]
    out["lisa_p"] = lm.p_sim
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
        "Statistically significant clusters of heat-equity risk\n"
        f"Local Moran, {PERMUTATIONS} permutations, p < {ALPHA}",
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

    w, note = build_weights(gdf)
    print(f"weights: {note}")

    print("\n=== global Moran's I ===")
    gm = global_moran(gdf, ["draft_score", *pcts], w)
    print(gm.round(4).to_string(index=False))
    print("\n(I = 0 would be spatial randomness; p is the permutation pseudo p-value)")

    print("\n=== local Moran (LISA) on draft_score ===")
    lisa = local_moran(gdf, "draft_score", w)
    print(lisa["lisa"].value_counts().to_string())
    write_processed(lisa, "spatial_lisa", config)

    print("\n--- spatial outliers: where the burden changes sharply ---")
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

    figures.save(figure_moran_scatter(lisa, "draft_score"), "spatial_moran_scatter")
    figures.save(figure_lisa_map(gdf, lisa, note), "spatial_lisa_map")
