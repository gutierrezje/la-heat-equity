"""The documented ArcGIS field contract matches the generated public schema."""

from pathlib import Path

import pandas as pd

from ccphit.config import load_config
from ccphit.product import export_columns


def test_public_contract_fields_are_unique_and_exported():
    contract = pd.read_csv(Path("config/arcgis_fields.csv"))
    assert contract["field"].is_unique
    assert contract["alias"].is_unique

    # export_columns only needs names for its dynamic heat-day discovery.
    layer_columns = [f"heat_day_{i}" for i in range(7)]
    exported = export_columns(load_config(), pd.DataFrame(columns=layer_columns))
    assert set(contract["field"]).issubset(exported)
