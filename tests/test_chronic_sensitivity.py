"""CDC-aligned chronic-pillar sensitivity."""

import pandas as pd

from ccphit.analysis.chronic_sensitivity import (
    CDC_ALIGNED,
    compare_chronic_designs,
    construct_chronic_sensitivity,
)


def frame():
    values = list(range(1, 7))
    data = {
        "zcta": [f"Z{i}" for i in values],
        "POP100": [100] * 6,
        "svi_pct": [10, 20, 30, 40, 50, 60],
        "chronic_pct": [10, 20, 30, 40, 50, 60],
        "historical_heat_er": values,
    }
    data.update({column: values for column in CDC_ALIGNED})
    data["poor_phys_health"] = values
    return pd.DataFrame(data)


def test_constructs_continuous_and_flag_alternatives():
    out = construct_chronic_sensitivity(frame())
    assert out["former_four_pct"].is_monotonic_increasing
    assert out["cdc_continuous_pct"].is_monotonic_increasing
    assert out["cdc_local_flag_mean"].iloc[0] == 0
    assert out["cdc_local_flag_mean"].iloc[-1] == 1
    assert out["cdc_local_flag_pct"].notna().all()


def test_comparison_reports_all_three_designs():
    out = compare_chronic_designs(construct_chronic_sensitivity(frame()))
    assert len(out) == 3
    assert out["n"].eq(6).all()
