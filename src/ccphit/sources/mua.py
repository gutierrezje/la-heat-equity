"""HRSA Medically Underserved Areas — the healthcare-access layer.

Substituted for HPSA, which the proposal named. HPSA turned out to be unusable at
county scale: of 44 Primary Care HPSA features intersecting the AOI, 30 are
"Proposed For Withdrawal" and only 3 of the remaining 14 are *area* designations —
the other 11 are population-group designations, which mean "low-income residents
within this area are underserved", not "this area is underserved". One of the 3 is in
Kern County, leaving two usable polygons for a 294-ZCTA county.

MUA is the sibling HRSA program with the same analytical purpose and workable
coverage: 56 features in the AOI, all Designated, 44 of them area-based. See D14.

Served from a MapServer rather than a FeatureServer — HRSA's
`.../HealthProfessionalShortageAreas_FS/FeatureServer` 500s with
"Server object extension 'featureserver' not found".
"""

import geopandas as gpd
import requests

from ccphit.config import load_config
from ccphit.io import pull_stamp, write_history, write_processed

# Area designations only. A "Medically Underserved Population" polygon designates a
# population group inside the boundary, so painting the whole ZCTA underserved from it
# would overstate the finding.
AREA_DESIGNATION = "Medically Underserved Area"


def fetch_mua(config: dict) -> gpd.GeoDataFrame:
    source = config["sources"]["mua"]
    minx, miny, maxx, maxy = config["aoi"]["bbox"]

    params = {
        "geometry": f"{minx},{miny},{maxx},{maxy}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "outSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        # Withdrawn and proposed-for-withdrawal designations are not current shortages.
        "where": (
            f"STATUS_DESCRIPTION='Designated' AND "
            f"DESIGNATION_TYPE_DESCRIPTION='{AREA_DESIGNATION}'"
        ),
        "outFields": "SOURCE_ID,SERVICE_AREA_NAME",
        "returnGeometry": "true",
        "f": "geojson",
    }
    response = requests.get(source["url"], params=params, timeout=90)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise Exception(data["error"]["message"])

    features = data.get("features", [])
    if not features:
        raise ValueError("MUA returned no designated area features for the AOI bbox")

    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    gdf = gdf.rename(
        columns={"SOURCE_ID": "mua_id", "SERVICE_AREA_NAME": "service_area"}
    )
    keep = [c for c in ("mua_id", "service_area") if c in gdf.columns]
    return gdf[[*keep, "geometry"]].reset_index(drop=True)


if __name__ == "__main__":
    config = load_config()
    mua = fetch_mua(config)
    write_processed(mua, "mua_areas", config)

    # Live service with no per-record date, so stamp the pull.
    write_history(mua, "mua_areas", config, stamp=pull_stamp())
