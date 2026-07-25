"""CalHeatScore source validation and pagination."""

import pandas as pd
import pytest
import requests

from ccphit.sources.calheatscore import (
    DAY_COLS,
    DAY_FIELDS,
    PAGE,
    TIMEOUT,
    HeatScoreSchemaError,
    fetch_heat_scores,
    normalize_heat_scores,
)

VERSION = "2.0"


def row(zip_code="90813", date="2026-07-25", days=(0, 1, 2, 3, 4, 3, 2)):
    return {"ZIP_CODE": zip_code, "DATE": date, **dict(zip(DAY_FIELDS, days))}


def config():
    return {
        "sources": {
            "calheatscore": {
                "url": "https://example.test/query",
                "method_version": VERSION,
            }
        }
    }


class Response:
    def __init__(self, payload, status_error=None):
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        return self.payload


def test_daily_values_and_descriptive_summaries_are_retained():
    out = normalize_heat_scores([row()], VERSION).iloc[0]
    assert out[DAY_COLS].tolist() == [0, 1, 2, 3, 4, 3, 2]
    assert out["heat_risk"] == 4
    assert out["heat_days_ge_3"] == 3
    assert out["heat_score_days"] == 15
    assert out["calheatscore_method_version"] == VERSION


def test_peak_and_duration_can_disagree():
    spike = normalize_heat_scores([row(days=(0, 0, 0, 4, 0, 0, 0))], VERSION).iloc[0]
    plateau = normalize_heat_scores([row(days=(3, 3, 3, 3, 3, 3, 3))], VERSION).iloc[0]
    assert spike["heat_risk"] > plateau["heat_risk"]
    assert spike["heat_days_ge_3"] < plateau["heat_days_ge_3"]
    assert spike["heat_score_days"] < plateau["heat_score_days"]


def test_string_scores_are_coerced_without_truncating_fractions():
    out = normalize_heat_scores(
        [row(days=("0", "1", "2", "3", "4", "3", "2"))], VERSION
    )
    assert out[DAY_COLS].dtypes.map(pd.api.types.is_integer_dtype).all()
    with pytest.raises(HeatScoreSchemaError, match="must be integers"):
        normalize_heat_scores([row(days=(0, 1, 2.5, 3, 4, 3, 2))], VERSION)


@pytest.mark.parametrize(
    ("bad_row", "message"),
    [
        ({}, "missing required"),
        (row(days=(0, 1, "n/a", 3, 4, 3, 2)), "non-numeric"),
        (row(days=(0, 1, 9, 3, 4, 3, 2)), "outside 0-4"),
        (row(zip_code="not-a-zip"), "invalid ZIP"),
    ],
)
def test_malformed_rows_are_rejected(bad_row, message):
    with pytest.raises(HeatScoreSchemaError, match=message):
        normalize_heat_scores([bad_row], VERSION)


def test_empty_and_duplicate_forecasts_are_rejected():
    with pytest.raises(HeatScoreSchemaError, match="no features"):
        normalize_heat_scores([], VERSION)
    with pytest.raises(HeatScoreSchemaError, match="duplicate ZIP"):
        normalize_heat_scores([row(), row()], VERSION)


def test_fetch_paginates_and_passes_timeout(monkeypatch):
    calls = []
    pages = [
        Response(
            {
                "features": [{"attributes": row("90813")}],
                "exceededTransferLimit": True,
            }
        ),
        Response({"features": [{"attributes": row("90210")}]}),
    ]

    def fake_get(url, params, timeout):
        calls.append((url, params, timeout))
        return pages.pop(0)

    monkeypatch.setattr("ccphit.sources.calheatscore.requests.get", fake_get)
    out = fetch_heat_scores(config())
    assert out["zip"].tolist() == ["90813", "90210"]
    assert [call[1]["resultOffset"] for call in calls] == [0, 1]
    assert all(call[1]["resultRecordCount"] == PAGE for call in calls)
    assert all(call[2] == TIMEOUT for call in calls)


def test_fetch_surfaces_http_and_service_errors(monkeypatch):
    def http_error(*args, **kwargs):
        return Response({}, requests.HTTPError("503"))

    monkeypatch.setattr("ccphit.sources.calheatscore.requests.get", http_error)
    with pytest.raises(requests.HTTPError, match="503"):
        fetch_heat_scores(config())

    def service_error(*args, **kwargs):
        return Response({"error": {"message": "bad query"}})

    monkeypatch.setattr("ccphit.sources.calheatscore.requests.get", service_error)
    with pytest.raises(HeatScoreSchemaError, match="bad query"):
        fetch_heat_scores(config())
