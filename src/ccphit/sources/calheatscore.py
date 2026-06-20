import requests
import pandas as pd

from ccphit.common import load_config, write_processed

def fetch_heat_scores(config: dict) -> pd.DataFrame:
    url = config["sources"]["calheatscore"]["url"]
    where = f"ZIP_CODE LIKE '90%'"
    params = {
        "where": where,
        "outFields": "*",
        "returnGeometry": "false",
        "f": "json",
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise Exception(data["error"]["message"])
    rows = [f["attributes"] for f in data["features"]]
    df = pd.DataFrame(rows)
    df["CHS_Day_0"] = df["CHS_Day_0"].astype(int)
    df["CHS_Day_1"] = df["CHS_Day_1"].astype(int)
    df["CHS_Day_2"] = df["CHS_Day_2"].astype(int)
    df["CHS_Day_3"] = df["CHS_Day_3"].astype(int)
    df["CHS_Day_4"] = df["CHS_Day_4"].astype(int)
    df["CHS_Day_5"] = df["CHS_Day_5"].astype(int)
    df["CHS_Day_6"] = df["CHS_Day_6"].astype(int)
    df = df.rename(columns={
        "ZIP_CODE": "zcta",
        "DATE": "date",
        "CHS_Day_0": "heat_risk_0",
    })
    df["zcta"] = df["zcta"].astype(str).str.zfill(5)
    return df[["zcta", "date", "heat_risk_0"]]

if __name__ == "__main__":
    config = load_config()
    heat_scores = fetch_heat_scores(config)
    write_processed(heat_scores, "heat_scores", config)