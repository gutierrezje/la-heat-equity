"""How much does the ranking depend on the weights we chose?

    uv run python -m ccphit.analysis.weight_sensitivity

The composite score's weights are a judgment call, and "are they defensible?" is the
open mentor question (D7). The strongest available answer is not a better guess — it is
showing that the answer barely depends on the guess.

Method: draw weight vectors uniformly from the simplex (Dirichlet(1,...,1)) and re-score
under each. Because the component percentiles are fixed — they are computed from the data,
not from the weights — re-scoring is a single matrix product, so tens of thousands of draws
cost milliseconds. The uniform draw is deliberately the *weakest* assumption: it admits
degenerate vectors like (1, 0, 0, 0). A ZCTA that stays in the top 10 across those is
robust for a much stronger reason than one that survives only small perturbations.

Reports, per ZCTA: the share of draws placing it in the top 10, and its best/median/worst
rank. Also, per component, the rank-weight correlation — which pillar is actually carrying
a given ZCTA's position.
"""

import numpy as np
import pandas as pd

from ccphit.config import load_config
from ccphit.io import read_processed, write_processed

DRAWS = 20_000
TOP_N = 10
SEED = 20260725


def sample_weights(n_components: int, draws: int, rng) -> np.ndarray:
    """Uniform over the simplex: every weighting summing to 1 is equally likely."""
    return rng.dirichlet(np.ones(n_components), size=draws)


def rank_stability(
    scored: pd.DataFrame,
    component_pcts: list[str],
    draws: int = DRAWS,
    top_n: int = TOP_N,
    seed: int = SEED,
    min_weight: float = 0.0,
) -> pd.DataFrame:
    """Rank every ZCTA under `draws` random weightings.

    `min_weight` restricts the draw to weightings where every pillar keeps at least that
    share. 0.0 is the unconstrained simplex, which admits degenerate vectors like
    (1, 0, 0, 0) — a deliberately hostile test. A floor of 0.10 approximates the space
    of weightings a reviewer would actually entertain.
    """
    usable = scored[scored[component_pcts].notna().all(axis=1)].copy()
    pcts = usable[component_pcts].to_numpy()  # (zctas, components)

    rng = np.random.default_rng(seed)
    weights = sample_weights(len(component_pcts), draws, rng)  # (draws, components)
    if min_weight > 0:
        # Rejection-sample rather than reshape the Dirichlet: keeps the draw uniform
        # over the *constrained* region instead of merely concentrated near the centre.
        keep = weights.min(axis=1) >= min_weight
        while keep.sum() < draws:
            extra = sample_weights(len(component_pcts), draws, rng)
            weights = np.vstack([weights[keep], extra])
            keep = weights.min(axis=1) >= min_weight
        weights = weights[keep][:draws]
    draws = len(weights)

    scores = pcts @ weights.T  # (zctas, draws)

    # rank 1 = highest score. argsort twice gives the rank of each row per column.
    order = np.argsort(-scores, axis=0)
    ranks = np.empty_like(order)
    np.put_along_axis(
        ranks, order, np.arange(1, len(usable) + 1)[:, None].repeat(draws, axis=1), axis=0
    )

    out = pd.DataFrame(
        {
            "zcta": usable["zcta"].to_numpy(),
            "top_n_share": (ranks <= top_n).mean(axis=1),
            "rank_best": ranks.min(axis=1),
            "rank_median": np.median(ranks, axis=1),
            "rank_worst": ranks.max(axis=1),
        }
    )

    # Which pillar carries this ZCTA's position? A negative correlation between a
    # weight and the rank number means raising that weight moves the ZCTA up the list.
    for i, col in enumerate(component_pcts):
        w = weights[:, i]
        wc = w - w.mean()
        rc = ranks - ranks.mean(axis=1, keepdims=True)
        denom = np.sqrt((rc**2).sum(axis=1) * (wc**2).sum())
        with np.errstate(invalid="ignore", divide="ignore"):
            out[f"driver_{col}"] = -np.where(denom > 0, (rc @ wc) / denom, np.nan)

    return out.sort_values("top_n_share", ascending=False).reset_index(drop=True)


if __name__ == "__main__":
    config = load_config()
    components = list(config["score"]["components"])
    component_pcts = [f"{name}_pct" for name in components]

    scored = read_processed(
        "zcta_scores", config, geo=True, require=["zcta", *component_pcts]
    )
    labels = scored[["zcta", "place_name", "POP100", "draft_score"]]

    scenarios = {
        "unconstrained": 0.0,  # hostile: admits (1, 0, 0, 0)
        "min10pct": 0.10,  # every pillar keeps a real say
    }
    reports = {}
    for label, floor in scenarios.items():
        stability = rank_stability(scored, component_pcts, min_weight=floor)
        report = stability.merge(labels, on="zcta", how="left")
        reports[label] = report

        always = int((report["top_n_share"] == 1.0).sum())
        never = int((report["top_n_share"] == 0.0).sum())
        print(f"\n=== {label} (min weight {floor:.0%}), {DRAWS:,} draws ===")
        print(f"ZCTAs ranked: {len(report)}")
        print(
            f"top {TOP_N} under EVERY weighting: {always}  |  under none: {never}  |  "
            f"weight-dependent: {len(report) - always - never}"
        )
        show = ["zcta", "place_name", "POP100", "top_n_share", "rank_best", "rank_worst"]
        print(report.head(10)[show].round(3).to_string(index=False))

    # Persist the constrained view; it is the one a reviewer would act on.
    out = reports["min10pct"].merge(
        reports["unconstrained"][["zcta", "top_n_share"]].rename(
            columns={"top_n_share": "top_n_share_unconstrained"}
        ),
        on="zcta",
        how="left",
    )
    write_processed(out, "weight_sensitivity", config)

    driver_cols = [c for c in out.columns if c.startswith("driver_")]
    print("\nrank-weight correlation — which pillar carries each of the top 8")
    print("(positive = raising that weight lifts this ZCTA; negative = it ranks high *despite* that pillar)")
    print(
        out.head(8)[["zcta", "place_name", *driver_cols]].round(2).to_string(index=False)
    )
