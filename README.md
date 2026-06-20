## Data sources status
### CalHeatScore: 
- Public ArcGIS FeatureServer, no uth.
- Daily refresh
- Fields: `ZIP_CODE`, `DATE`, `CHS_Day_0`-`CHS_Day_6` (string)
- Scale: (0-4) heat-health risk
- Tabular only; geometry joined later via ZCTA boundaries
- Output: tabular `heat_score.parquet`
- Note: source uses ZIP codes, not ZCTA. Crosswalk later