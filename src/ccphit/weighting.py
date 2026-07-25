"""Population weighting — the methodology that distinguishes this pipeline (see D8).

Weighting is applied at three layers: the tract->ZCTA crosswalk (value), the
distance origin (location), and the score percentiles (ranking). This module
holds the ranking piece.
"""

import pandas as pd


def pop_weighted_pct(values: pd.Series, pop: pd.Series) -> pd.Series:
    """Percentile rank weighted by population (midpoint rule). Higher value → higher pct.

    Tied values receive the mean percentile of their tie group.
    """
    out = pd.Series(index=values.index, dtype=float)
    valid = values.notna() & pop.notna() & (pop > 0)
    if not valid.any():
        return out

    # Aggregate population per distinct value *before* ranking. Ranking row-by-row
    # and averaging within a tie group makes the result depend on row order, which
    # matters here because heat_risk is an integer 0-4 and is almost all ties.
    df = pd.DataFrame({"v": values[valid], "p": pop[valid]})
    by_value = df.groupby("v", sort=True)["p"].sum().sort_index()
    pct = (by_value.cumsum() - 0.5 * by_value) / by_value.sum() * 100

    out.loc[df.index] = df["v"].map(pct)
    return out
