"""How certain is the response-versus-investment recommendation?

    uv run python -m ccphit.analysis.candidate_uncertainty

`validation.py` compares four candidate score designs against LA County's historical
excess-ER heat measure and reports one rank correlation each. Those four numbers carry
the report's central recommendation — that the current four-pillar index mixes two
decisions and should be split — but they are reported without uncertainty, so a reader
cannot tell whether 0.52 and 0.74 are meaningfully different or the same number twice.

Two gaps are closed here.

**Uncertainty.** Each correlation gets a percentile bootstrap confidence interval by
resampling ZIP-code areas with replacement. No distributional assumption, and the
procedure is explainable in one sentence: *if we had drawn a different sample of
neighbourhoods, how much would this number move?*

**Comparison.** The candidates are scored on the *same* areas against the *same*
benchmark, so their correlations are statistically dependent and cannot be compared as
if independent. Bootstrapping the **difference** handles the dependence directly: each
resample recomputes both correlations on the same resampled areas, so the pairing is
preserved. A difference interval excluding zero means the designs genuinely disagree.

**Sample alignment.** `validation.py` computes each candidate on its own complete rows,
so "susceptibility only" used 285 areas and the others 282. Comparing correlations
measured on different samples confounds design with coverage, so everything here runs on
the common complete subset.
"""

import numpy as np
import pandas as pd

from ccphit.analysis import figures
from ccphit.config import load_config
from ccphit.io import read_processed, write_processed

BENCHMARK = "historical_heat_er"
BOOTSTRAP = 5_000
SEED = 20260725
CI = 95
BASELINE = "current four-pillar"


def candidate_scores(d: pd.DataFrame) -> dict[str, pd.Series]:
    """Mirrors `validation.candidate_score_comparison`; kept in step deliberately."""
    return {
        BASELINE: d["draft_score"],
        "three equal pillars": (d["heat_pct"] + d["svi_pct"] + d["chronic_pct"]) / 3,
        "response: 50% heat": (
            0.50 * d["heat_pct"] + 0.25 * d["svi_pct"] + 0.25 * d["chronic_pct"]
        ),
        "susceptibility only": (d["svi_pct"] + d["chronic_pct"]) / 2,
    }


def leave_one_pillar_out(d: pd.DataFrame, pillars: list[str]) -> dict[str, pd.Series]:
    """Single-factor contrasts: the full index, and the index with one pillar removed.

    The candidates in `validation.py` differ in more than one way at a time — "three
    equal pillars" both drops the resource gap *and* reweights heat — so a difference
    between two of them cannot be attributed to either change. Removing exactly one
    pillar at a time isolates what each contributes.
    """
    out = {"all four pillars": d[pillars].mean(axis=1)}
    for p in pillars:
        rest = [c for c in pillars if c != p]
        out[f"without {p.replace('_pct', '')}"] = d[rest].mean(axis=1)
    return out


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Rank correlation via ranks + Pearson, so it is fast enough to bootstrap."""
    ra = pd.Series(a).rank().to_numpy()
    rb = pd.Series(b).rank().to_numpy()
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    denom = np.sqrt((ra**2).sum() * (rb**2).sum())
    return float((ra @ rb) / denom) if denom else np.nan


def bootstrap_correlations(
    scores: dict[str, pd.Series],
    benchmark: pd.Series,
    draws: int = BOOTSTRAP,
    seed: int = SEED,
) -> pd.DataFrame:
    """Resample areas with replacement; recompute every candidate on the same draw."""
    names = list(scores)
    X = np.column_stack([scores[n].to_numpy() for n in names])
    y = benchmark.to_numpy()
    n = len(y)

    rng = np.random.default_rng(seed)
    out = np.empty((draws, len(names)))
    for b in range(draws):
        idx = rng.integers(0, n, n)
        yb = y[idx]
        for j in range(len(names)):
            out[b, j] = spearman(X[idx, j], yb)
    return pd.DataFrame(out, columns=names)


def summarize(observed: dict[str, float], boot: pd.DataFrame, ci: int = CI) -> pd.DataFrame:
    lo, hi = (100 - ci) / 2, 100 - (100 - ci) / 2
    rows = []
    for name in boot.columns:
        draws = boot[name].to_numpy()
        rows.append(
            {
                "candidate": name,
                "rho": observed[name],
                f"ci{ci}_low": np.percentile(draws, lo),
                f"ci{ci}_high": np.percentile(draws, hi),
                "bootstrap_sd": draws.std(ddof=1),
            }
        )
    return pd.DataFrame(rows)


def paired_differences(
    observed: dict[str, float], boot: pd.DataFrame, baseline: str = BASELINE, ci: int = CI
) -> pd.DataFrame:
    """Bootstrap the difference, preserving the pairing across resamples."""
    lo, hi = (100 - ci) / 2, 100 - (100 - ci) / 2
    rows = []
    for name in boot.columns:
        if name == baseline:
            continue
        diff = (boot[name] - boot[baseline]).to_numpy()
        low, high = np.percentile(diff, lo), np.percentile(diff, hi)
        rows.append(
            {
                "candidate": name,
                "rho_difference": observed[name] - observed[baseline],
                f"ci{ci}_low": low,
                f"ci{ci}_high": high,
                # Two-sided bootstrap p: how often does the difference cross zero?
                "p_two_sided": 2 * min((diff <= 0).mean(), (diff >= 0).mean()),
                "excludes_zero": bool(low > 0 or high < 0),
            }
        )
    return pd.DataFrame(rows)


def figure_intervals(summary: pd.DataFrame, diffs: pd.DataFrame, ci: int = CI):
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.4), width_ratios=[1, 1])

    ax = axes[0]
    order = summary.sort_values("rho")
    y = np.arange(len(order))
    ax.hlines(y, order[f"ci{ci}_low"], order[f"ci{ci}_high"], lw=3, color=figures.MUTED)
    colors = [
        figures.PALETTE["urban"] if c == BASELINE else figures.INK
        for c in order["candidate"]
    ]
    ax.scatter(order["rho"], y, s=45, color=colors, zorder=3)
    ax.set_yticks(y, order["candidate"])
    ax.set_xlabel(f"rank agreement with historical harm ({ci}% CI)")
    ax.set_title("Every candidate, with uncertainty")
    figures.annotate(ax, "red = current index", "lower right")

    ax = axes[1]
    order = diffs.sort_values("rho_difference")
    y = np.arange(len(order))
    ax.axvline(0, lw=1.2, ls="--", color=figures.MUTED)
    ax.hlines(y, order[f"ci{ci}_low"], order[f"ci{ci}_high"], lw=3, color=figures.MUTED)
    ax.scatter(
        order["rho_difference"], y, s=45, zorder=3,
        color=[
            figures.PALETTE["urban"] if e else figures.MUTED
            for e in order["excludes_zero"]
        ],
    )
    ax.set_yticks(y, order["candidate"])
    ax.set_xlabel(f"difference vs the current index ({ci}% CI)")
    ax.set_title("Which designs genuinely differ?")
    figures.annotate(ax, "interval clear of 0 = real difference", "lower right")

    fig.suptitle(
        "The split recommendation rests on these gaps being real, not noise", y=1.04
    )
    return fig


if __name__ == "__main__":
    import matplotlib.pyplot as plt  # noqa: E402

    figures.setup()
    config = load_config()

    d = read_processed("external_validation", config, require=["zcta", BENCHMARK])
    scores = candidate_scores(d)

    # Common complete subset: comparing correlations measured on different samples
    # would confound the design with which areas each design happens to cover.
    complete = d[BENCHMARK].notna()
    for s in scores.values():
        complete &= s.notna()
    d, n_all = d[complete], len(d)
    scores = {k: v[complete] for k, v in scores.items()}
    print(f"common complete subset: {len(d)} of {n_all} ZCTAs")
    print(f"(validation.py reports 282-285 per candidate; aligning costs "
          f"{285 - len(d)} area(s) but makes the comparison valid)\n")

    observed = {k: spearman(v.to_numpy(), d[BENCHMARK].to_numpy()) for k, v in scores.items()}
    boot = bootstrap_correlations(scores, d[BENCHMARK])

    summary = summarize(observed, boot)
    print(f"=== rank agreement with historical harm ({BOOTSTRAP:,} bootstrap draws) ===")
    print(summary.round(3).to_string(index=False))

    diffs = paired_differences(observed, boot)
    print(f"\n=== difference from '{BASELINE}' (paired bootstrap) ===")
    print(diffs.round(4).to_string(index=False))

    print("\n=== reading ===")
    for r in diffs.itertuples():
        verdict = (
            "genuinely better" if r.excludes_zero and r.rho_difference > 0
            else "genuinely worse" if r.excludes_zero
            else "NOT distinguishable from the current index"
        )
        print(f"  {r.candidate:22s} {r.rho_difference:+.3f}  -> {verdict}")

    write_processed(summary, "candidate_uncertainty", config)
    write_processed(diffs, "candidate_uncertainty_differences", config)
    figures.save(figure_intervals(summary, diffs), "candidate_uncertainty")

    # --- single-factor decomposition -------------------------------------------------
    # The candidates above differ in more than one way at once, so their gaps cannot be
    # attributed to a specific pillar. Drop exactly one pillar at a time instead.
    pillars = [f"{n}_pct" for n in config["score"]["components"]]
    loo = leave_one_pillar_out(d, pillars)
    loo_observed = {
        k: spearman(v.to_numpy(), d[BENCHMARK].to_numpy()) for k, v in loo.items()
    }
    loo_boot = bootstrap_correlations(loo, d[BENCHMARK])
    loo_diffs = paired_differences(loo_observed, loo_boot, baseline="all four pillars")

    print("\n=== which pillar is dragging historical agreement down? ===")
    print("(equal-weight index, one pillar removed at a time)\n")
    print(summarize(loo_observed, loo_boot).round(3).to_string(index=False))
    print("\ndifference from the full four-pillar equal-weight index:")
    print(loo_diffs.round(4).to_string(index=False))
    print("\n=== reading ===")
    for r in loo_diffs.itertuples():
        if not r.excludes_zero:
            verdict = "no detectable effect either way"
        elif r.rho_difference > 0:
            verdict = "REMOVING it improves agreement — this pillar is the drag"
        else:
            verdict = "removing it hurts — this pillar is carrying signal"
        print(f"  {r.candidate:28s} {r.rho_difference:+.3f}  -> {verdict}")

    write_processed(loo_diffs, "candidate_pillar_contribution", config)
