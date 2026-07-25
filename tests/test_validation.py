"""External-validation summaries."""

import pandas as pd
import pytest

from ccphit.analysis.validation import (
    candidate_score_comparison,
    priority_set_comparison,
    top_set_agreement,
    validation_correlations,
)


def frame():
    return pd.DataFrame(
        {
            "zcta": [f"Z{i}" for i in range(6)],
            "POP100": [10, 20, 30, 40, 50, 60],
            "heat_risk": [1, 2, 3, 4, 4, 4],
            "heat_pct": [10, 20, 30, 70, 80, 90],
            "svi_pct": [10, 20, 30, 70, 80, 90],
            "chronic_pct": [10, 20, 30, 70, 80, 90],
            "resource_gap_pct": [90, 80, 70, 30, 20, 10],
            "draft_score": [10, 20, 30, 70, 80, 90],
            "historical_heat_er": [1, 2, 3, 4, 5, 6],
        }
    )


def test_correlations_preserve_direction_and_report_n():
    out = validation_correlations(frame()).set_index("measure")
    assert out.loc["svi_pct", "spearman_rho"] == pytest.approx(1.0)
    assert out.loc["resource_gap_pct", "spearman_rho"] == pytest.approx(-1.0)
    assert out["n"].eq(6).all()


def test_top_set_agreement_uses_equal_sized_sets():
    out = top_set_agreement(frame(), "draft_score", "historical_heat_er", 0.5)
    assert out["n_top"] == 3
    assert out["overlap"] == 3
    assert out["jaccard"] == 1


def test_priority_comparison_counts_residents_not_index_points():
    out = priority_set_comparison(frame())
    assert out["current_zctas"] == 2
    assert out["current_population"] == 110
    assert out["historical_zctas"] == 2
    assert out["historical_population"] == 110
    assert out["overlap_zctas"] == 2


def test_candidate_comparison_reports_all_transparent_designs():
    out = candidate_score_comparison(frame())
    assert set(out["candidate"]) == {
        "current four-pillar",
        "three equal pillars",
        "response: 50% heat",
        "susceptibility only",
    }
    assert out["n"].eq(6).all()
