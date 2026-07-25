"""Compare the current chronic pillar with a CDC Heat & Health Index-aligned set.

This is a sensitivity analysis, not a silent production change. The CDC-aligned set is
CHD, obesity, diabetes, COPD, asthma, and poor mental health. Because the national
tertile cut points are not distributed with this local extract, the flag experiment uses
LA County population-weighted tertiles and is labeled as a local approximation.
"""

import pandas as pd

from ccphit.analysis import figures
from ccphit.config import load_config
from ccphit.io import read_processed, write_processed
from ccphit.weighting import pop_weighted_pct

CURRENT = ["asthma", "copd", "diabetes", "poor_phys_health"]
CDC_ALIGNED = ["chd", "obesity", "diabetes", "copd", "asthma", "poor_mental_health"]


def construct_chronic_sensitivity(d: pd.DataFrame) -> pd.DataFrame:
    """Build continuous and local-tertile CDC-aligned alternatives."""
    out = d.copy()
    population = out["POP100"]
    former_ranked = pd.DataFrame(
        {column: pop_weighted_pct(out[column], population) for column in CURRENT}
    )
    out["former_four_pct"] = former_ranked.mean(axis=1)
    ranked = pd.DataFrame(
        {column: pop_weighted_pct(out[column], population) for column in CDC_ALIGNED}
    )
    out["cdc_continuous_pct"] = ranked.mean(axis=1)
    flags = (ranked >= (100 * 2 / 3)).astype(float)
    flags[ranked.isna()] = float("nan")
    out["cdc_local_flag_mean"] = flags.mean(axis=1)
    out["cdc_local_flag_pct"] = pop_weighted_pct(
        out["cdc_local_flag_mean"],
        population,
    )
    return out


def compare_chronic_designs(d: pd.DataFrame) -> pd.DataFrame:
    designs = {
        "former four-condition mean": "former_four_pct",
        "CDC-aligned continuous mean": "cdc_continuous_pct",
        "CDC-aligned local-tertile flags": "cdc_local_flag_pct",
    }
    rows = []
    for label, column in designs.items():
        valid = d[[column, "svi_pct", "historical_heat_er"]].dropna()
        rows.append(
            {
                "design": label,
                "rho_svi": valid[column].corr(valid["svi_pct"], method="spearman"),
                "rho_historical_harm": valid[column].corr(
                    valid["historical_heat_er"], method="spearman"
                ),
                "n": len(valid),
            }
        )
    return pd.DataFrame(rows)


def figure_chronic(comparison: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.3))
    labels = [
        "former\n4-condition",
        "CDC-aligned\ncontinuous",
        "CDC-aligned\nlocal flags",
    ]
    for ax, column, title in [
        (axes[0], "rho_svi", "Overlap with social vulnerability"),
        (axes[1], "rho_historical_harm", "Agreement with historical heat harm"),
    ]:
        bars = ax.bar(labels, comparison[column], color=figures.PALETTE["urban"])
        ax.set_ylim(0, 0.9)
        ax.set_ylabel("Spearman rank correlation")
        ax.set_title(title)
        for bar, value in zip(bars, comparison[column]):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 0.025,
                f"{value:.2f}",
                ha="center",
                fontsize=9,
                weight="bold",
            )
    fig.suptitle(
        "Changing the condition list does not remove the demographic overlap",
        y=1.02,
        weight="bold",
    )
    return fig


if __name__ == "__main__":
    import matplotlib.pyplot as plt  # noqa: E402

    figures.setup()
    cfg = load_config()
    places = read_processed(
        "places_zcta",
        cfg,
        require=["zcta", *set(CURRENT + CDC_ALIGNED)],
    )
    scored = read_processed(
        "external_validation",
        cfg,
        require=["zcta", "POP100", "svi_pct", "chronic_pct", "historical_heat_er"],
    )
    missing_columns = [
        column for column in set(CURRENT + CDC_ALIGNED) if column not in scored.columns
    ]
    result = scored.copy()
    if missing_columns:
        result = result.merge(
            places[["zcta", *missing_columns]],
            on="zcta",
            how="left",
            validate="1:1",
        )
    result = construct_chronic_sensitivity(result)
    comparison = compare_chronic_designs(result)
    print(comparison.round(3).to_string(index=False))
    write_processed(
        result[
            [
                "zcta",
                "cdc_continuous_pct",
                "former_four_pct",
                "cdc_local_flag_mean",
                "cdc_local_flag_pct",
            ]
        ],
        "chronic_sensitivity",
        cfg,
    )
    write_processed(comparison, "chronic_sensitivity_comparison", cfg)
    figures.save(figure_chronic(comparison), "chronic_sensitivity")
