# ArcGIS product contract

The final product is one StoryMap, one Dashboard, and two hosted layers. The
Dashboard and StoryMap should read fields from the layers; they should not
reimplement classification logic.

## Hosted layers

1. **ZCTA heat-equity layer** — `data/processed/zcta_scores.geojson`
2. **Cooling-center locations** — `data/processed/cooling_centers.geojson`

Keep these as separate layers. A polygon answers “where are conditions most
concerning?” A point answers “where is a listed service and what are its hours?”
Joining the facility attributes to polygons would obscure multiple sites and
make operating details harder to maintain.

## Dashboard structure

Use two selectors or tabs over the same ZCTA layer.

### Current response

- Map style: unique values on `response_category`.
- Headline filter: `response_priority = 1`.
- Indicator: sum `POP100` after that filter, labelled “Residents in current
  response-priority areas.”
- Secondary indicator: count of `zcta`.
- Popup order: place, ZCTA, current seven-day peak (`heat_risk`), days at
  CalHeatScore 3+ (`heat_days_ge_3`), SVI percentile (`svi_pct`), chronic
  percentile (`chronic_pct`), response category.
- Trend/chart: `heat_day_0` through `heat_day_6`. Label these with the forecast
  dates in the surrounding StoryMap text; field names are offsets, not dates.
- Optional scalar sorting: `response_index`. Do not present it as expected
  cases or affected residents.

The response-priority rule is intentionally readable: **CalHeatScore 4 and
upper-third social vulnerability**.

### Long-term investment

- Map style: unique values on `investment_category`.
- Headline filter: `investment_priority = 1`.
- Indicator: sum `POP100`, labelled “Residents in long-term
  investment-priority areas.”
- Popup order: place, ZCTA, historical excess-ER heat score
  (`historical_heat_er`), SVI percentile, vegetation shade at 3 p.m.
  (`vegetation_shade_pct`), investment category.

The investment screen requires **upper-third historical heat harm,
upper-third social vulnerability, and lower-third vegetation shade**. It is a
transparent screening rule, not an estimate of illnesses prevented by planting.

### Facility panel

Display the cooling-center point layer above both views. The list widget should
show `site_name`, `address`, and `days_hours_of_operation`. Make the source/run
date visible. Do not rank ZCTAs by straight-line distance: the live list is
volatile and distance is not access, capacity, travel time, or availability.

## StoryMap sequence

1. **The policy distinction:** emergency response this week is not the same
   question as long-term heat investment.
2. **Current conditions:** embed the Dashboard on the response view; explain
   the forecast date and the two-factor category.
3. **Why vulnerability matters:** show the historical validation figure and
   explain rank correlation in one sentence: areas with higher vulnerability
   tend to rank higher in historical heat-related emergency-room harm.
4. **Structural investment:** embed the investment view and explain the
   three-factor screen.
5. **What people can use now:** cooling-center map/list with the volatility and
   hours caveat.
6. **Methods and limitations:** link the research report, source dates, code,
   and decisions log.

## Field aliases and formats

Set these aliases once in the hosted feature layer, then preserve the item ID
through overwrites. The same contract is available for scripts and QA at
`config/arcgis_fields.csv`.

| Field | ArcGIS alias | Format/use |
|---|---|---|
| `zcta` | ZIP Code Tabulation Area | text |
| `place_name` | Community or city | text |
| `POP100` | 2020 population | integer, comma-separated |
| `forecast_date` | Forecast issued | date |
| `heat_risk` | Peak 7-day CalHeatScore | 0 decimals |
| `heat_days_ge_3` | Days at CalHeatScore 3+ | integer |
| `svi_pct` | Social vulnerability percentile | 0–100, 1 decimal |
| `chronic_pct` | Chronic susceptibility percentile | 0–100, 1 decimal |
| `historical_heat_er` | Historical excess-ER heat score | 1 decimal |
| `vegetation_shade_pct` | Vegetation shade at 3 p.m. | percent, 1 decimal |
| `response_index` | Current response index | 0–100, 1 decimal; secondary |
| `response_category` | Current response category | unique-value renderer |
| `response_priority` | Current response priority | hidden 0/1 filter |
| `investment_category` | Long-term investment category | unique-value renderer |
| `investment_priority` | Long-term investment priority | hidden 0/1 filter |
| `dist_m` | Nearest listed center distance | metres; context only |
| `draft_score` | Legacy four-pillar draft score | hidden during migration |

## Migration and refresh

1. Run `uv run python -m ccphit.run`.
2. Check the two priority counts printed by the `product` stage.
3. Run `uv run python -m ccphit.publish --dry-run`.
4. On the first schema-changing update, export a backup of the hosted layer and
   verify field aliases and renderers in a staging web map.
5. Overwrite the existing hosted layer so downstream item IDs remain stable.
6. Update widgets to the category/priority fields above.
7. Hide, then later remove, `draft_score` and `resource_gap_pct` after no widget
   references them.

The publisher validates that the six fields required for the two views exist
before it authenticates or changes ArcGIS.
