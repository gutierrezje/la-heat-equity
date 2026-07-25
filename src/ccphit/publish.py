"""Publish the scored layer to ArcGIS Online as an idempotent overwrite.

    uv run python -m ccphit.publish --dry-run   # validate, change nothing
    uv run python -m ccphit.publish             # overwrite the hosted layer

Deliberately **not** a stage in `ccphit.run`. Refreshing local data and mutating a
public layer are different kinds of action, and the second should never happen as a
side effect of the first.

Why overwrite rather than delete-and-recreate: `overwrite()` retains the item's
`itemID`, metadata, and configured capabilities. The web map, Dashboard, and StoryMap
all reference the layer *by item id*, so recreating it would silently break every
downstream artifact.

Constraints inherited from the ArcGIS API (see FeatureLayerCollectionManager.overwrite):
  1. The target must be a hosted feature layer collection.
  2. The uploaded file must have the **same filename** as the one originally used to
     publish the item — hence `zcta_scores.geojson`, unchanged.
  3. Schema changes (added columns) are tolerated on ArcGIS Online but not on older
     Enterprise. The first publish after a schema change is the risky one; a pure data
     refresh is safe.

Credentials are never read from config or arguments. Either store a named profile once
(preferred, keeps secrets in the OS keyring):

    python -c "from arcgis.gis import GIS; GIS('https://www.arcgis.com', 'USER', 'PASS', profile='ccphit')"

then export ``ARCGIS_PROFILE=ccphit``; or export ``ARCGIS_URL`` / ``ARCGIS_USER`` /
``ARCGIS_PASSWORD`` for a one-off run.
"""

import argparse
import os
import sys
from pathlib import Path

import geopandas as gpd

from ccphit.config import load_config, processed_dir

LAYER_ARTIFACT = "zcta_scores"


def connect():
    """Authenticate to ArcGIS Online from the environment, never from config."""
    from arcgis.gis import GIS

    profile = os.environ.get("ARCGIS_PROFILE")
    if profile:
        return GIS(profile=profile)

    url = os.environ.get("ARCGIS_URL", "https://www.arcgis.com")
    user = os.environ.get("ARCGIS_USER")
    password = os.environ.get("ARCGIS_PASSWORD")
    if not (user and password):
        raise SystemExit(
            "No ArcGIS credentials found. Set ARCGIS_PROFILE (preferred), or "
            "ARCGIS_USER and ARCGIS_PASSWORD. See this module's docstring."
        )
    return GIS(url, user, password)


def describe_local(config: dict) -> tuple[Path, gpd.GeoDataFrame]:
    """Validate the artifact we are about to upload, before touching the network."""
    path = processed_dir(config) / f"{LAYER_ARTIFACT}.geojson"
    if not path.exists():
        raise SystemExit(
            f"{path} does not exist. Run the pipeline first: "
            f"uv run python -m ccphit.run"
        )

    gdf = gpd.read_file(path)
    print(f"local artifact : {path} ({path.stat().st_size / 1e6:.1f} MB)")
    print(f"  features     : {len(gdf)}")
    print(f"  fields       : {len(gdf.columns) - 1}")
    if "forecast_date" in gdf.columns:
        print(f"  forecast_date: {as_of(gdf)}")
    if "draft_score" in gdf.columns:
        scored = gdf["draft_score"].notna().sum()
        print(f"  scored       : {scored}/{len(gdf)} ({len(gdf) - scored} no-data)")
    return path, gdf


def as_of(gdf: gpd.GeoDataFrame) -> str:
    """Latest forecast date as YYYY-MM-DD.

    GDAL infers a date type when reading the GeoJSON back, so the value may arrive as
    a Timestamp rather than the string that was written.
    """
    if "forecast_date" not in gdf.columns:
        return "unknown"
    dates = sorted(gdf["forecast_date"].dropna().unique())
    return str(dates[-1])[:10] if dates else "unknown"


def item_summary(gdf: gpd.GeoDataFrame) -> dict:
    """Item metadata that states what the layer reflects, since a viewer cannot tell.

    Metadata is an explicit assignment requirement and easy to leave stale; deriving
    it from the data keeps it honest.
    """
    as_of_date = as_of(gdf)
    return {
        "snippet": (
            f"LA County heat-equity risk by ZCTA. Heat forecast as of {as_of_date}; "
            f"cooling-center access as of the same pipeline run."
        ),
        "description": (
            "Composite heat-equity risk score for Los Angeles County ZIP Code "
            "Tabulation Areas, combining forecast heat-health risk (CalHeatScore), "
            "social vulnerability (CDC/ATSDR SVI 2022, population-weighted areal "
            "interpolation from census tracts), chronic disease prevalence (CDC "
            "PLACES 2024), and straight-line distance to the nearest cooling center. "
            "<br/><br/><b>Read the score as an intensity, not a count</b> — a high "
            "score means conditions are worse there, not that more people are "
            "affected. Distance to cooling centers is straight-line and reflects the "
            "cooling-center layer on the run date, which changes over time. "
            f"<br/><br/>Heat forecast as of {as_of_date}. Produced from code; see the "
            "project repository for methodology."
        ),
    }


def publish(config: dict, dry_run: bool) -> int:
    path, gdf = describe_local(config)

    item_id = config.get("publish", {}).get("item_id")
    if not item_id:
        raise SystemExit(
            "config.yml has no publish.item_id. Add the item id of the hosted feature "
            "layer to overwrite (the long hex string in its ArcGIS Online URL). "
            "Publishing a brand-new item is intentionally not automated — do the first "
            "publish by hand, then record its id here so every later run overwrites it."
        )

    gis = connect()
    print(f"connected as   : {gis.users.me.username} ({gis.properties.get('urlKey', gis.url)})")

    item = gis.content.get(item_id)
    if item is None:
        raise SystemExit(f"No item {item_id} visible to this account.")
    print(f"target item    : {item.title!r} ({item.type})")

    if item.type != "Feature Service":
        raise SystemExit(
            f"Item {item_id} is a {item.type!r}, not a Feature Service; overwrite only "
            "works on hosted feature layer collections."
        )

    if dry_run:
        print("\ndry run — nothing was modified.")
        print(f"would overwrite {item.title!r} from {path.name}")
        print("would refresh item snippet/description with:")
        print(f"  {item_summary(gdf)['snippet']}")
        return 0

    from arcgis.features import FeatureLayerCollection

    flc = FeatureLayerCollection.fromitem(item)
    print(f"\noverwriting from {path.name} ...")
    result = flc.manager.overwrite(str(path))

    if not (isinstance(result, dict) and result.get("success")):
        print(f"✗ overwrite failed: {result}", file=sys.stderr)
        return 1

    item.update(item_properties=item_summary(gdf))
    print("✓ overwrite succeeded; item metadata refreshed")
    print(f"  {item.homepage}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate credentials, item, and local artifact without modifying anything",
    )
    args = parser.parse_args(argv)
    return publish(load_config(), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
