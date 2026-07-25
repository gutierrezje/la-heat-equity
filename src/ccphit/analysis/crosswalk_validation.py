"""Does population weighting in the tract->ZCTA crosswalk actually change anything?

    uv run python -m ccphit.analysis.crosswalk_validation

The crosswalk is the declared engineering centerpiece (D5, D8), and until now it was
invisible: nothing in the Dashboard or StoryMap showed that the choice of weighting
mattered, so the claim rested on assertion. This quantifies it by running the same
interpolation three ways on the same geometry and comparing:

  population-weighted   what the pipeline ships (D8)
  area-weighted         the earlier draft (D5), and what a naive implementation does
  centroid join         the fallback D5 rejected — assign each tract wholly to whichever
                        ZCTA contains its centroid

Writes a per-ZCTA comparison and a two-panel figure for the StoryMap methods section.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from ccphit.config import CRS_M, load_config, processed_dir
from ccphit.conform.tract_to_zcta import interpolate_to_zcta
from ccphit.io import read_processed, write_processed

VALUE = "svi"


def area_weighted(tracts: gpd.GeoDataFrame, zctas: gpd.GeoDataFrame) -> pd.DataFrame:
    """The D5 draft: weight each overlap piece by area, ignoring who lives there."""
    t = tracts[["tract_geoid", VALUE, "geometry"]].to_crs(CRS_M)
    z = zctas[["zcta", "geometry"]].to_crs(CRS_M)

    ix = gpd.overlay(t, z, how="intersection", keep_geom_type=False)
    ix["w"] = ix.geometry.area
    ix["wv"] = ix[VALUE] * ix["w"]
    g = ix.groupby("zcta", as_index=False).agg(wv=("wv", "sum"), w=("w", "sum"))
    g[f"{VALUE}_area"] = g["wv"] / g["w"]
    return g[["zcta", f"{VALUE}_area"]]


def centroid_join(tracts: gpd.GeoDataFrame, zctas: gpd.GeoDataFrame) -> pd.DataFrame:
    """The fallback D5 rejected: each tract counts wholly for one ZCTA."""
    t = tracts[["tract_geoid", VALUE, "pop", "geometry"]].to_crs(CRS_M).copy()
    t["geometry"] = t.geometry.centroid
    z = zctas[["zcta", "geometry"]].to_crs(CRS_M)

    joined = gpd.sjoin(t, z, how="inner", predicate="within")
    joined["wv"] = joined[VALUE] * joined["pop"]
    g = joined.groupby("zcta", as_index=False).agg(wv=("wv", "sum"), w=("pop", "sum"))
    g[f"{VALUE}_centroid"] = g["wv"] / g["w"]
    return g[["zcta", f"{VALUE}_centroid"]]


def compare(tracts: gpd.GeoDataFrame, zctas: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    pop = interpolate_to_zcta(tracts, zctas, value_cols=[VALUE]).rename(
        columns={VALUE: f"{VALUE}_pop"}
    )
    out = pop.merge(area_weighted(tracts, zctas), on="zcta", how="left")
    out = out.merge(centroid_join(tracts, zctas), on="zcta", how="left")

    out["diff_area"] = out[f"{VALUE}_pop"] - out[f"{VALUE}_area"]
    out["diff_centroid"] = out[f"{VALUE}_pop"] - out[f"{VALUE}_centroid"]
    return gpd.GeoDataFrame(out, geometry="geometry", crs=pop.crs)


def summarize(cmp: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for label, col in [("area-weighted", "diff_area"), ("centroid join", "diff_centroid")]:
        d = cmp[col].dropna()
        other = cmp[f"{VALUE}_{'area' if 'area' in col else 'centroid'}"]
        rows.append(
            {
                "alternative": label,
                "n_compared": len(d),
                "n_missing": int(other.isna().sum()),
                "mean_abs_diff": d.abs().mean(),
                "p90_abs_diff": d.abs().quantile(0.90),
                "max_abs_diff": d.abs().max(),
                "spearman_vs_pop": cmp[f"{VALUE}_pop"].corr(other, method="spearman"),
            }
        )
    return pd.DataFrame(rows)


def figure(cmp: gpd.GeoDataFrame, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(13, 6))

    ax = axes[0]
    ax.scatter(cmp[f"{VALUE}_area"], cmp[f"{VALUE}_pop"], s=14, alpha=0.6)
    lim = [0, 1]
    ax.plot(lim, lim, lw=1, ls="--", color="0.4")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("SVI, area-weighted (the naive result)")
    ax.set_ylabel("SVI, population-weighted (shipped)")
    ax.set_title("Same geometry, two weightings")

    ax = axes[1]
    cmp.plot(
        column="diff_area",
        cmap="RdBu_r",
        vmin=-0.25,
        vmax=0.25,
        legend=True,
        linewidth=0.1,
        edgecolor="white",
        ax=ax,
        missing_kwds={"color": "0.9"},
    )
    ax.set_axis_off()
    ax.set_title("Where they disagree\n(red = population weighting raises SVI)")

    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


if __name__ == "__main__":
    config = load_config()
    tracts = read_processed(
        "svi_tracts", config, geo=True, require=["tract_geoid", "pop", VALUE]
    )
    zctas = read_processed("zcta_bounds", config, geo=True, require=["zcta", "POP100"])

    cmp = compare(tracts, zctas)
    write_processed(cmp.drop(columns="geometry"), "crosswalk_validation", config)

    print("\nhow much does the weighting choice matter?")
    print(summarize(cmp).round(4).to_string(index=False))

    named = cmp.merge(
        read_processed("zcta_scores", config, geo=True)[
            ["zcta", "place_name", "POP100"]
        ],
        on="zcta",
        how="left",
    )
    worst = named.reindex(named["diff_area"].abs().sort_values(ascending=False).index)
    print("\nZCTAs where population weighting changes SVI most vs area weighting:")
    print(
        worst.head(8)[
            ["zcta", "place_name", "POP100", f"{VALUE}_area", f"{VALUE}_pop", "diff_area"]
        ]
        .round(3)
        .to_string(index=False)
    )

    # Does the disagreement concentrate in low-density ZCTAs, as D8 predicted?
    with_area = named.copy()
    with_area["km2"] = with_area.to_crs(CRS_M).geometry.area / 1e6
    with_area["density"] = with_area["POP100"] / with_area["km2"]
    valid = with_area[with_area["density"] > 0].dropna(subset=["diff_area"])
    r = np.log10(valid["density"]).corr(valid["diff_area"].abs(), method="spearman")
    print(f"\nSpearman(|diff|, log population density) = {r:+.3f}")
    print("negative => the two methods diverge most in sparsely populated ZCTAs (D8's claim)")

    out_png = processed_dir(config) / "crosswalk_validation.png"
    figure(cmp, out_png)
    print(f"\nfigure -> {out_png}")
