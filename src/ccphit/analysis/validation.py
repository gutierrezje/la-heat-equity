"""Compare the current index with LA County's historical excess-ER heat geography.

This is criterion validation, not another score component. It asks a policy-readable
question: do the places forecast to be hottest this week resemble the places where heat
has historically produced excess emergency-room visits?
"""

import numpy as np
import pandas as pd

from ccphit.analysis import figures
from ccphit.analysis.equity import classify_priority_cells
from ccphit.config import load_config
from ccphit.conform.tract_to_zcta import interpolate_to_zcta
from ccphit.io import read_processed, write_processed

MEASURES = {
    "heat_risk": "current forecast peak",
    "svi_pct": "social vulnerability",
    "chronic_pct": "chronic disease",
    "resource_gap_pct": "listed-centre distance",
    "draft_score": "four-pillar index",
}


def validation_correlations(d: pd.DataFrame) -> pd.DataFrame:
    """Spearman rank agreement with historical excess-ER heat."""
    rows = []
    for column, label in MEASURES.items():
        pair = d[[column, "historical_heat_er"]].dropna()
        rows.append(
            {
                "measure": column,
                "label": label,
                "spearman_rho": pair[column].corr(
                    pair["historical_heat_er"], method="spearman"
                ),
                "n": len(pair),
            }
        )
    return pd.DataFrame(rows)


def candidate_score_comparison(d: pd.DataFrame) -> pd.DataFrame:
    """Compare simple score designs with historical harm.

    Historical agreement is diagnostic, not the sole selection rule: an operational
    response index should still react to the current forecast.
    """
    candidates = {
        "current four-pillar": d["draft_score"],
        "three equal pillars": (
            d["heat_pct"] + d["svi_pct"] + d["chronic_pct"]
        )
        / 3,
        "response: 50% heat": (
            0.50 * d["heat_pct"]
            + 0.25 * d["svi_pct"]
            + 0.25 * d["chronic_pct"]
        ),
        "susceptibility only": (d["svi_pct"] + d["chronic_pct"]) / 2,
    }
    rows = []
    for label, score in candidates.items():
        pair = pd.DataFrame(
            {"candidate": score, "historical_heat_er": d["historical_heat_er"]}
        ).dropna()
        rows.append(
            {
                "candidate": label,
                "historical_rho": pair["candidate"].corr(
                    pair["historical_heat_er"], method="spearman"
                ),
                "n": len(pair),
            }
        )
    return pd.DataFrame(rows)


def top_set_agreement(
    d: pd.DataFrame, left: str, right: str, fraction: float
) -> dict[str, float]:
    """Agreement between equally sized top-ranked sets."""
    pair = d[["zcta", left, right]].dropna()
    n_top = max(1, int(np.floor(len(pair) * fraction)))
    a = set(pair.nlargest(n_top, left)["zcta"])
    b = set(pair.nlargest(n_top, right)["zcta"])
    overlap = len(a & b)
    return {
        "fraction": fraction,
        "n_complete": len(pair),
        "n_top": n_top,
        "overlap": overlap,
        "jaccard": overlap / len(a | b),
    }


def priority_set_comparison(d: pd.DataFrame) -> dict[str, int]:
    """Compare current and historical high-heat/high-vulnerability categories."""
    cells = d.dropna(subset=["zcta", "POP100", "svi_pct"]).copy()
    svi_cut = cells["svi_pct"].quantile(2 / 3)
    high_svi = cells["svi_pct"] >= svi_cut
    historical_band = pd.qcut(
        cells["historical_heat_er"],
        3,
        labels=["lower third", "middle third", "upper third"],
    )
    current = set(
        cells.loc[
            high_svi & cells["heat_risk"].notna() & (cells["heat_risk"] == 4),
            "zcta",
        ]
    )
    historical = set(
        cells.loc[high_svi & (historical_band == "upper third"), "zcta"]
    )
    pop = cells.set_index("zcta")["POP100"]
    return {
        "current_zctas": len(current),
        "current_population": int(pop.loc[list(current)].sum()),
        "historical_zctas": len(historical),
        "historical_population": int(pop.loc[list(historical)].sum()),
        "overlap_zctas": len(current & historical),
    }


def figure_validation(d: pd.DataFrame, correlations: pd.DataFrame):
    """One figure carrying the core validation result without specialist notation."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), width_ratios=[1.2, 1.2, 1])

    ax = axes[0]
    forecast_groups = [
        d.loc[d["heat_risk"] == score, "historical_heat_er"].dropna()
        for score in sorted(d["heat_risk"].dropna().unique())
    ]
    labels = [str(int(score)) for score in sorted(d["heat_risk"].dropna().unique())]
    ax.boxplot(forecast_groups, tick_labels=labels, showfliers=False)
    ax.set_xlabel("current seven-day peak CalHeatScore")
    ax.set_ylabel("historical excess-ER heat score")
    ax.set_title("This week's forecast only weakly\nresembles historical harm")

    ax = axes[1]
    cells = classify_priority_cells(d)
    svi_groups = [
        cells.loc[cells["svi_band"] == band, "historical_heat_er"].dropna()
        for band in ["lower third", "middle third", "upper third"]
    ]
    ax.boxplot(
        svi_groups,
        tick_labels=["lower", "middle", "upper"],
        showfliers=False,
    )
    ax.set_xlabel("social vulnerability rank")
    ax.set_ylabel("historical excess-ER heat score")
    ax.set_title("Historical harm rises sharply\nwith vulnerability")

    ax = axes[2]
    ordered = correlations.sort_values("spearman_rho")
    colors = [
        figures.PALETTE["urban"] if value >= 0 else figures.PALETTE["remote"]
        for value in ordered["spearman_rho"]
    ]
    ax.barh(ordered["label"], ordered["spearman_rho"], color=colors)
    ax.axvline(0, color=figures.INK, lw=0.7)
    ax.set_xlim(-0.8, 0.8)
    ax.set_xlabel("rank agreement with historical harm")
    ax.set_title("What aligns with observed harm?")
    for y, value in enumerate(ordered["spearman_rho"]):
        ax.text(
            value + (0.025 if value >= 0 else -0.025),
            y,
            f"{value:+.2f}",
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=8,
        )

    fig.suptitle(
        "Forecast severity and historical heat harm are different maps",
        y=1.02,
        fontsize=15,
        weight="bold",
    )
    return fig


def build_validation(config: dict) -> pd.DataFrame:
    outcomes = read_processed(
        "county_heat_tracts",
        config,
        require=["tract_geoid", "historical_heat_er", "historical_heat_tercile"],
    )
    tracts = read_processed(
        "svi_tracts",
        config,
        geo=True,
        require=["tract_geoid", "pop"],
    )
    zctas = read_processed(
        "zcta_bounds",
        config,
        geo=True,
        require=["zcta"],
    )
    scored = read_processed(
        "zcta_scores",
        config,
        geo=True,
        require=["zcta", "heat_risk", "heat_pct", *MEASURES],
    )

    joined = tracts[["tract_geoid", "pop", "geometry"]].merge(
        outcomes[["tract_geoid", "historical_heat_er", "historical_heat_tercile"]],
        on="tract_geoid",
        how="inner",
        validate="1:1",
    )
    historical = interpolate_to_zcta(
        joined,
        zctas,
        value_cols=["historical_heat_er"],
    ).drop(columns="geometry")
    validation = scored.merge(historical, on="zcta", how="left", validate="1:1")
    return validation


if __name__ == "__main__":
    import matplotlib.pyplot as plt  # noqa: E402

    figures.setup()
    cfg = load_config()
    result = build_validation(cfg)
    correlations = validation_correlations(result)
    print("\n=== rank agreement with historical excess-ER heat ===")
    print(correlations.round(3).to_string(index=False))

    print("\n=== top-set agreement ===")
    agreements = pd.DataFrame(
        [
            top_set_agreement(result, "draft_score", "historical_heat_er", 0.10),
            top_set_agreement(result, "draft_score", "historical_heat_er", 1 / 3),
        ]
    )
    print(agreements.round(3).to_string(index=False))

    comparison = priority_set_comparison(result)
    print("\n=== high vulnerability + high heat ===")
    for key, value in comparison.items():
        print(f"{key:24s} {value:,}")

    candidates = candidate_score_comparison(result)
    print("\n=== candidate score designs vs historical harm ===")
    print(candidates.round(3).to_string(index=False))

    write_processed(
        result.drop(columns="geometry"),
        "external_validation",
        cfg,
    )
    write_processed(correlations, "external_validation_correlations", cfg)
    write_processed(candidates, "candidate_score_validation", cfg)
    figures.save(figure_validation(result, correlations), "external_validation")
