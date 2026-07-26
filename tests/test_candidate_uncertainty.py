"""Guards for the bootstrap comparison behind the response-versus-investment split."""

import numpy as np
import pandas as pd
import pytest

from ccphit.analysis.candidate_uncertainty import (
    bootstrap_correlations,
    leave_one_pillar_out,
    paired_differences,
    spearman,
    summarize,
)

PILLARS = ["heat_pct", "svi_pct", "chronic_pct", "resource_gap_pct"]


def frame(n=120, seed=0):
    rng = np.random.default_rng(seed)
    benchmark = rng.normal(size=n)
    return pd.DataFrame(
        {
            "historical_heat_er": benchmark,
            # one pillar tracks the benchmark, one is inverted, two are noise
            "svi_pct": benchmark + rng.normal(scale=0.4, size=n),
            "resource_gap_pct": -benchmark + rng.normal(scale=0.4, size=n),
            "heat_pct": rng.normal(size=n),
            "chronic_pct": rng.normal(size=n),
        }
    )


# --- spearman ------------------------------------------------------------------------


def test_spearman_matches_pandas():
    d = frame()
    expected = d["svi_pct"].corr(d["historical_heat_er"], method="spearman")
    assert spearman(d["svi_pct"].to_numpy(), d["historical_heat_er"].to_numpy()) == pytest.approx(
        expected, abs=1e-9
    )


def test_spearman_is_rank_based_not_scale_based():
    a = np.array([1.0, 2.0, 3.0, 4.0])
    assert spearman(a, a**5) == pytest.approx(1.0)


def test_spearman_of_a_constant_is_undefined_not_zero():
    assert np.isnan(spearman(np.ones(10), np.arange(10.0)))


# --- bootstrap -----------------------------------------------------------------------


def test_bootstrap_interval_brackets_the_observed_value():
    d = frame()
    scores = {"svi": d["svi_pct"]}
    observed = {"svi": spearman(d["svi_pct"].to_numpy(), d["historical_heat_er"].to_numpy())}
    boot = bootstrap_correlations(scores, d["historical_heat_er"], draws=400)
    s = summarize(observed, boot).iloc[0]
    assert s["ci95_low"] < s["rho"] < s["ci95_high"]


def test_bootstrap_is_reproducible_for_a_fixed_seed():
    d = frame()
    scores = {"svi": d["svi_pct"]}
    a = bootstrap_correlations(scores, d["historical_heat_er"], draws=200, seed=5)
    b = bootstrap_correlations(scores, d["historical_heat_er"], draws=200, seed=5)
    pd.testing.assert_frame_equal(a, b)


def test_a_larger_sample_gives_a_tighter_interval():
    small = frame(n=60, seed=1)
    large = frame(n=600, seed=1)
    widths = []
    for d in (small, large):
        obs = {"svi": spearman(d["svi_pct"].to_numpy(), d["historical_heat_er"].to_numpy())}
        boot = bootstrap_correlations({"svi": d["svi_pct"]}, d["historical_heat_er"], draws=400)
        s = summarize(obs, boot).iloc[0]
        widths.append(s["ci95_high"] - s["ci95_low"])
    assert widths[1] < widths[0]


# --- paired differences --------------------------------------------------------------


def test_a_candidate_compared_with_itself_shows_no_difference():
    """The pairing must be preserved across resamples, or this would show noise."""
    d = frame()
    scores = {"base": d["svi_pct"], "copy": d["svi_pct"].copy()}
    obs = {k: spearman(v.to_numpy(), d["historical_heat_er"].to_numpy()) for k, v in scores.items()}
    boot = bootstrap_correlations(scores, d["historical_heat_er"], draws=400)
    diff = paired_differences(obs, boot, baseline="base").iloc[0]

    assert diff["rho_difference"] == pytest.approx(0.0, abs=1e-12)
    assert not diff["excludes_zero"]


def test_a_genuinely_better_candidate_is_detected():
    d = frame(n=300)
    scores = {"noise": d["heat_pct"], "signal": d["svi_pct"]}
    obs = {k: spearman(v.to_numpy(), d["historical_heat_er"].to_numpy()) for k, v in scores.items()}
    boot = bootstrap_correlations(scores, d["historical_heat_er"], draws=600)
    diff = paired_differences(obs, boot, baseline="noise").iloc[0]

    assert diff["rho_difference"] > 0
    assert diff["excludes_zero"]
    assert diff["p_two_sided"] < 0.05


def test_the_baseline_is_excluded_from_its_own_comparison():
    d = frame()
    scores = {"base": d["svi_pct"], "other": d["heat_pct"]}
    obs = {k: spearman(v.to_numpy(), d["historical_heat_er"].to_numpy()) for k, v in scores.items()}
    boot = bootstrap_correlations(scores, d["historical_heat_er"], draws=200)
    out = paired_differences(obs, boot, baseline="base")
    assert out["candidate"].tolist() == ["other"]


# --- leave one pillar out ------------------------------------------------------------


def test_leave_one_out_produces_the_full_index_plus_one_design_per_pillar():
    designs = leave_one_pillar_out(frame(), PILLARS)
    assert len(designs) == len(PILLARS) + 1
    assert "all four pillars" in designs
    for p in PILLARS:
        assert f"without {p.replace('_pct', '')}" in designs


def test_removing_an_inverted_pillar_improves_agreement():
    """The substantive result: a pillar pointing the wrong way subtracts signal."""
    d = frame(n=400)
    designs = leave_one_pillar_out(d, PILLARS)
    obs = {k: spearman(v.to_numpy(), d["historical_heat_er"].to_numpy()) for k, v in designs.items()}
    assert obs["without resource_gap"] > obs["all four pillars"]


def test_removing_a_signal_carrying_pillar_hurts():
    d = frame(n=400)
    designs = leave_one_pillar_out(d, PILLARS)
    obs = {k: spearman(v.to_numpy(), d["historical_heat_er"].to_numpy()) for k, v in designs.items()}
    assert obs["without svi"] < obs["all four pillars"]
