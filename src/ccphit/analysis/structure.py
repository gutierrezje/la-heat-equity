"""Is the composite score well specified, and how many dimensions does it really have?

    uv run python -m ccphit.analysis.structure

Three questions, in order:

1. **Are the four pillars independent?** If two of them measure the same thing, the score
   silently over-weights that thing regardless of what `config.yml` says.
2. **How many effective dimensions?** A composite is only honest if the things it adds up
   are actually separate.
3. **Do the dimensions correspond to recognisable kinds of place?** If so the county has a
   *typology*, which is more actionable for outreach than a ranked list.

The interesting property of this module is that it reaches D18's conclusion — two
high-risk geographies with opposite drivers — by a completely different route. D18 got
there by resampling weights; PCA gets there from the covariance structure alone.
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from ccphit.analysis import figures
from ccphit.config import load_config
from ccphit.io import read_processed, write_processed

K = 4
SEED = 7

# Assigned after inspecting the k=4 profiles; see REPORT.md.
ARCHETYPES = {
    "urban_vulnerable": "Dense & vulnerable, well served",
    "remote_underserved": "Remote & underserved",
    "hot_not_vulnerable": "Hot but not vulnerable",
    "lower_risk": "Lower risk",
}


def variance_inflation(X: np.ndarray) -> list[float]:
    """VIF per column, computed by least squares rather than by importing statsmodels."""
    out = []
    for i in range(X.shape[1]):
        others = np.delete(X, i, axis=1)
        beta, *_ = np.linalg.lstsq(others, X[:, i], rcond=None)
        resid = X[:, i] - others @ beta
        ss_tot = ((X[:, i] - X[:, i].mean()) ** 2).sum()
        r2 = 1 - (resid**2).sum() / ss_tot
        out.append(1 / (1 - r2) if r2 < 1 else np.inf)
    return out


def name_clusters(profiles: pd.DataFrame, pcts: list[str]) -> dict[int, str]:
    """Label clusters by their own shape, not by a hand-typed cluster number.

    Cluster ids from k-means are arbitrary and change with the seed, so deriving the
    label from the profile keeps the naming reproducible.
    """
    heat, svi, chronic, gap = pcts
    names = {}
    for cid, row in profiles.iterrows():
        vulnerable = (row[svi] + row[chronic]) / 2
        if vulnerable > 60:
            key = "urban_vulnerable"
        elif row[gap] > 65:
            key = "remote_underserved"
        elif row[heat] > 55:
            key = "hot_not_vulnerable"
        else:
            key = "lower_risk"
        names[cid] = key
    return names


def figure_redundancy(corr: pd.DataFrame, vifs: list[float], pcts: list[str]):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), width_ratios=[1.15, 1])

    ax = axes[0]
    im = ax.imshow(corr.to_numpy(), cmap=figures.DIVERGE_CMAP, vmin=-1, vmax=1)
    short = [c.replace("_pct", "") for c in pcts]
    ax.set_xticks(range(len(short)), short, rotation=30, ha="right")
    ax.set_yticks(range(len(short)), short)
    for i in range(len(short)):
        for j in range(len(short)):
            v = corr.iloc[i, j]
            ax.text(
                j, i, f"{v:.2f}", ha="center", va="center", fontsize=9,
                color="white" if abs(v) > 0.55 else figures.INK,
                weight="bold" if (abs(v) > 0.7 and i != j) else "normal",
            )
    ax.set_title("Pillar correlation (Spearman)")
    fig.colorbar(im, ax=ax, shrink=0.8)

    ax = axes[1]
    bars = ax.barh(short, vifs, color=figures.MUTED)
    bars[int(np.argmax(vifs))].set_color(figures.PALETTE["urban"])
    ax.axvline(5, ls="--", lw=1, color=figures.PALETTE["urban"])
    ax.text(5.05, -0.4, "conventional concern threshold", fontsize=7.5, color=figures.MUTED)
    ax.set_xlabel("variance inflation factor")
    ax.set_title("Collinearity among pillars")
    ax.set_xlim(0, max(6, max(vifs) * 1.25))

    fig.suptitle("Two of the four pillars measure much the same thing", y=1.03)
    return fig


def figure_pca(pcs: pd.DataFrame, loadings: pd.DataFrame, evr: np.ndarray, pcts: list[str]):
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2), width_ratios=[1, 1.25])

    ax = axes[0]
    ax.bar(range(1, len(evr) + 1), evr * 100, color=figures.MUTED)
    ax.plot(
        range(1, len(evr) + 1), np.cumsum(evr) * 100, "o-",
        color=figures.PALETTE["urban"], lw=1.5, ms=4,
    )
    ax.axhline(100, lw=0.5, color=figures.MUTED)
    ax.set_xticks(range(1, len(evr) + 1))
    ax.set_xlabel("principal component")
    ax.set_ylabel("% of variance (bars) / cumulative (line)")
    ax.set_title("Not one axis, but two")
    figures.annotate(ax, f"PC1+PC2 = {np.cumsum(evr)[1]:.0%}", "upper left")

    ax = axes[1]
    for key, sub in pcs.groupby("archetype"):
        ax.scatter(
            sub["PC1"], sub["PC2"], s=np.sqrt(sub["POP100"]) / 4,
            alpha=0.75, label=ARCHETYPES[key], color=figures.PALETTE[
                {"urban_vulnerable": "urban", "remote_underserved": "remote",
                 "hot_not_vulnerable": "hot_only", "lower_risk": "low"}[key]
            ],
            edgecolor="white", linewidth=0.4,
        )
    scale = 3.0
    for var in pcts:
        x, y = loadings.loc[var, "PC1"] * scale, loadings.loc[var, "PC2"] * scale
        ax.arrow(0, 0, x, y, color=figures.INK, width=0.012, head_width=0.1, alpha=0.75)
        ax.text(x * 1.12, y * 1.12, var.replace("_pct", ""), fontsize=8.5, weight="bold")

    for zc, lbl in [("90201", "Bell"), ("93543", "Antelope Valley"), ("90813", "Long Beach")]:
        r = pcs[pcs["zcta"] == zc]
        if len(r):
            ax.annotate(
                lbl, (r["PC1"].iloc[0], r["PC2"].iloc[0]),
                textcoords="offset points", xytext=(6, 5), fontsize=8, weight="bold",
            )
    ax.axhline(0, lw=0.5, color=figures.MUTED)
    ax.axvline(0, lw=0.5, color=figures.MUTED)
    ax.set_xlabel("PC1 — vulnerability & disease  (vs. good access)")
    ax.set_ylabel("PC2 — heat & remoteness")
    ax.set_title("Two independent routes to high risk\n(point size = population)")
    ax.legend(loc="lower right")

    fig.suptitle("The composite hides which mechanism is operating", y=1.0)
    return fig


def figure_profiles(profiles: pd.DataFrame, names: dict, pcts: list[str], sizes: pd.Series):
    short = [c.replace("_pct", "") for c in pcts]
    fig, ax = plt.subplots(figsize=(9.5, 4.4))

    width = 0.2
    x = np.arange(len(short))
    key_for_color = {
        "urban_vulnerable": "urban", "remote_underserved": "remote",
        "hot_not_vulnerable": "hot_only", "lower_risk": "low",
    }
    for i, (cid, row) in enumerate(profiles.iterrows()):
        key = names[cid]
        ax.bar(
            x + (i - 1.5) * width, [row[c] for c in pcts], width,
            label=f"{ARCHETYPES[key]}  (n={int(sizes[cid])}, {row['pop_share']:.0%} of pop)",
            color=figures.PALETTE[key_for_color[key]], edgecolor="white", linewidth=0.5,
        )
    ax.axhline(50, ls="--", lw=1, color=figures.MUTED)
    ax.text(len(short) - 0.45, 51, "county median", fontsize=7.5, color=figures.MUTED)
    ax.set_xticks(x, short)
    ax.set_ylabel("mean population-weighted percentile")
    ax.set_title("Four kinds of at-risk place — needing different interventions")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2)
    return fig


if __name__ == "__main__":
    import matplotlib.pyplot as plt  # noqa: E402  (after figures.setup sets the backend)

    figures.setup()
    config = load_config()
    pcts = [f"{n}_pct" for n in config["score"]["components"]]

    scored = read_processed("zcta_scores", config, geo=True, require=["zcta", *pcts])
    d = scored.dropna(subset=pcts).reset_index(drop=True)
    print(f"n = {len(d)} scored ZCTAs")

    X = StandardScaler().fit_transform(d[pcts])

    # --- 1. redundancy
    corr = d[pcts].corr(method="spearman")
    vifs = variance_inflation(X)
    print("\n=== 1. are the pillars independent? ===")
    print(corr.round(2).to_string())
    worst = corr.where(~np.eye(len(pcts), dtype=bool)).stack().idxmax()
    print(f"\nmost redundant pair: {worst[0]} / {worst[1]} = {corr.loc[worst]:.2f}")
    for c, v in zip(pcts, vifs):
        print(f"  VIF {c:20s} {v:.2f}")

    # --- 2. dimensionality
    pca = PCA().fit(X)
    evr = pca.explained_variance_ratio_
    loadings = pd.DataFrame(pca.components_[:2].T, index=pcts, columns=["PC1", "PC2"])
    print("\n=== 2. how many dimensions? ===")
    for i, (e, c) in enumerate(zip(evr, np.cumsum(evr)), 1):
        print(f"  PC{i}: {e:.1%}  cumulative {c:.1%}")
    print("\nloadings:")
    print(loadings.round(2).to_string())

    # --- 3. typology
    print("\n=== 3. does the county have a typology? ===")
    print(" k  silhouette")
    for k in range(2, 8):
        lab = KMeans(n_clusters=k, n_init=25, random_state=SEED).fit_predict(X)
        print(f" {k}  {silhouette_score(X, lab):.3f}")

    km = KMeans(n_clusters=K, n_init=50, random_state=SEED).fit(X)
    d["cluster"] = km.labels_
    scores = pca.transform(X)[:, :2]
    d["PC1"], d["PC2"] = scores[:, 0], scores[:, 1]

    profiles = d.groupby("cluster")[[*pcts, "draft_score"]].mean()
    sizes = d.groupby("cluster").size()
    profiles["pop_share"] = d.groupby("cluster")["POP100"].sum() / d["POP100"].sum()
    names = name_clusters(profiles, pcts)
    d["archetype"] = d["cluster"].map(names)

    print(f"\nk={K} profiles:")
    labelled = profiles.copy()
    labelled.index = [ARCHETYPES[names[i]] for i in profiles.index]
    print(labelled.round(1).to_string())
    print("\nexemplars:")
    for cid in sorted(d["cluster"].unique()):
        sub = d[d["cluster"] == cid].nlargest(4, "draft_score")
        print(f"  {ARCHETYPES[names[cid]]:36s} "
              + ", ".join(f"{r.place_name}" for r in sub.itertuples()))

    out = d[["zcta", "place_name", "POP100", "draft_score", "archetype", "PC1", "PC2"]]
    write_processed(out, "structure_typology", config)

    figures.save(figure_redundancy(corr, vifs, pcts), "structure_redundancy")
    figures.save(figure_pca(d, loadings, evr, pcts), "structure_pca")
    figures.save(figure_profiles(profiles, names, pcts, sizes), "structure_archetypes")
