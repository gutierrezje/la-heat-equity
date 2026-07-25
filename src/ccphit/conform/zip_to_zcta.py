"""ZIP grain -> ZCTA grain: attach CalHeatScore's per-ZIP forecast to ZCTA polygons.

Direct 5-digit match. USPS ZIPs and Census ZCTAs are distinct systems; unmatched
ZCTAs are left as no-data rather than imputed (see D4).
"""

import geopandas as gpd
import pandas as pd

from ccphit.config import load_config
from ccphit.io import read_processed, write_processed


def attach_heat_scores(
    la_zctas: gpd.GeoDataFrame, heat_scores: pd.DataFrame
) -> gpd.GeoDataFrame:
    la_zctas = la_zctas.copy()
    heat_scores = heat_scores.copy()

    merged = la_zctas.merge(
        heat_scores, left_on="zcta", right_on="zip", how="left", validate="1:1"
    )
    merged = merged.drop(columns=["zip"])

    matched = merged["heat_risk"].notna().sum()
    print(f"heat match: {matched}/{len(merged)} ZCTAs")
    unmatched = merged.loc[merged["heat_risk"].isna(), "zcta"].tolist()
    print(f"unmatched ZCTAs ({len(unmatched)}):", unmatched)

    return merged


if __name__ == "__main__":
    config = load_config()
    la_zctas = read_processed(
        "zcta_bounds", config, geo=True, require=["zcta", "POP100"]
    )
    heat_scores = read_processed(
        "heat_scores", config, require=["zip", "forecast_date", "heat_risk"]
    )

    zcta_heat_scores = attach_heat_scores(la_zctas, heat_scores)
    write_processed(zcta_heat_scores, "zcta_heat_scores", config)
