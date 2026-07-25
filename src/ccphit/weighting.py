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
    ranked = pd.DataFrame({"v": values[valid], "p": pop[valid]}).sort_values("v")
    cum = ranked["p"].cumsum()
    ranked["pct"] = (cum - 0.5 * ranked["p"]) / ranked["p"].sum() * 100
    ranked["pct"] = ranked.groupby("v", sort=False)["pct"].transform("mean")
    out.loc[ranked.index] = ranked["pct"]
    return out
