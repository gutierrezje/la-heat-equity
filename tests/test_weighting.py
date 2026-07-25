"""Population-weighted percentile ranking (D8)."""

import pandas as pd
import pytest

from ccphit.weighting import pop_weighted_pct


def test_tied_values_are_order_independent():
    """Regression: ranking row-by-row then averaging made ties order-dependent.

    Two units tied at the same value with populations 1 and 100 scored 25.5 or
    74.5 purely on sort order. Both must now be the group midpoint, 50.
    """
    low_first = pd.DataFrame({"v": [2, 2], "p": [1, 100]})
    high_first = pd.DataFrame({"v": [2, 2], "p": [100, 1]})

    a = pop_weighted_pct(low_first["v"], low_first["p"])
    b = pop_weighted_pct(high_first["v"], high_first["p"])

    assert a.tolist() == b.tolist() == [50.0, 50.0]


def test_all_values_tied_puts_everything_at_the_midpoint():
    """The saturation case: on an extreme forecast most ZCTAs share heat_risk 4."""
    v = pd.Series([4, 4, 4, 4])
    p = pd.Series([10, 500, 3, 90])
    assert pop_weighted_pct(v, p).tolist() == [50.0, 50.0, 50.0, 50.0]


def test_distinct_values_use_population_midpoints():
    v = pd.Series([1, 2, 3])
    p = pd.Series([10, 10, 10])
    result = pop_weighted_pct(v, p)
    assert result.round(3).tolist() == [16.667, 50.0, 83.333]


def test_ranking_reflects_people_not_places():
    """90% of the population sits at the lowest value, so it ranks near-median."""
    v = pd.Series([1, 2])
    p = pd.Series([90, 10])
    assert pop_weighted_pct(v, p).tolist() == [45.0, 95.0]


def test_unpopulated_and_missing_units_are_excluded_not_imputed():
    v = pd.Series([1.0, 2.0, None, 3.0])
    p = pd.Series([10, 0, 10, 10])  # index 1 has no residents, index 2 no value
    result = pop_weighted_pct(v, p)

    assert result.isna().tolist() == [False, True, True, False]
    # The two survivors split the population between them.
    assert result.dropna().round(3).tolist() == [25.0, 75.0]


def test_no_valid_rows_returns_all_na():
    v = pd.Series([None, None], dtype=float)
    p = pd.Series([10, 10])
    assert pop_weighted_pct(v, p).isna().all()


@pytest.mark.parametrize("n", [1, 2, 50])
def test_output_is_always_bounded_to_a_percentile(n):
    v = pd.Series(range(n))
    p = pd.Series([7] * n)
    result = pop_weighted_pct(v, p).dropna()
    assert ((result >= 0) & (result <= 100)).all()
