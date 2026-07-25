## Data sources status

### CalHeatScore ✅
- Public ArcGIS FeatureServer, no auth
- Daily refresh (~5am & 8am PT)
- Fields: `ZIP_CODE`, `DATE`, `CHS_Day_0`–`CHS_Day_6` (string → int)
- Scale: 0–4 heat-health risk; `heat_risk` = max over 7-day forecast
- Tabular only; joined to ZCTAs via direct `zip == zcta` match (approximation)
- Output: `data/processed/heat_scores.parquet`
- Note: source uses USPS ZIP codes, not Census ZCTA

### CDC/ATSDR SVI 2022 ✅ (local download)
- **Not** an API — California census-tract File Geodatabase downloaded from [CDC SVI](https://www.atsdr.cdc.gov/placeandhealth/svi/data_documentation_download.html)
- Local path: `data/raw/SVI2022_CALIFORNIA_tract.gdb` (layer `SVI2022_CALIFORNIA_tract`)
- Native unit: census tract (11-digit `FIPS` / GEOID)
- Key field: `RPL_THEMES` — overall social vulnerability percentile (0–1; higher = more vulnerable)
- Missing data sentinel: `-999` (excluded before processing)
- Scope filter: `FIPS` starts with `06037` (Los Angeles County)
- CRS: EPSG:4269 in source → reprojected to EPSG:4326 in pipeline
- Join strategy: tract values allocated to ZCTAs via population-weighted areal interpolation (`conform/tract_to_zcta.py`, EPSG:3310)
- Output: `data/processed/svi_tracts.parquet` → `data/processed/zcta_svi.parquet`