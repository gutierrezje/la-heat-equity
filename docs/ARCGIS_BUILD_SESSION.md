# ArcGIS assembly session

This is the shortest safe path from the generated files to the final StoryMap
and Dashboard. Follow it in order. Do not redesign the methods during the build.

## Before opening ArcGIS — 10 minutes

This submission is a fixed case study of the forecast issued **25 July 2026**.
It is not a live-conditions product. From the repository root, rebuild from the
archived forecast rather than fetching a new one:

```bash
cp data/processed/heat_scores.parquet /tmp/heat_scores_before_storymap.parquet
cp data/history/heat_scores_2026-07-25.parquet data/processed/heat_scores.parquet
uv run python -m ccphit.run --from zip_to_zcta
uv run pytest -q
```

Confirm that the rebuilt `zcta_scores.geojson` reports `forecast_date` as
`2026-07-25`. The `/tmp` copy preserves a newer processed forecast, if one
existed, for restoration after the build.

Use these fixed case-study values:

- short-term response: 16 ZCTAs and 878,241 residents;
- long-term investment: 36 ZCTAs and 1,723,130 residents.

Confirm these files exist:

```text
data/processed/zcta_scores.geojson
data/processed/cooling_centers.geojson
docs/figures/external_validation.png
docs/figures/shade_equity.png
docs/figures/equity_priority_population.png
docs/STORYMAP_COPY.md
config/arcgis_fields.csv
```

## Part 1 — Hosted layers

### ZCTA layer

Use the existing hosted ZCTA item if one already powers the Dashboard. Preserve
its item ID.

1. Export or download a backup of the hosted item.
2. Confirm `config.yml` contains its `publish.item_id`.
3. Run:

   ```bash
   uv run python -m ccphit.publish --dry-run
   uv run python -m ccphit.publish
   ```

4. If no item ID exists, publish `zcta_scores.geojson` manually once, paste the
   new item ID into `config.yml`, and use overwrite for later refreshes.
5. Set field aliases from `config/arcgis_fields.csv`.
6. Hide `draft_score`, `resource_gap_pct`, and `dist_m` from default popups.
   Retain them temporarily until every old widget has been migrated.

### Cooling-center layer

Publish or overwrite `cooling_centers.geojson` as a separate hosted point
layer. Configure its popup:

```text
Title: {site_name}
Address: {address}
Hours: {days_hours_of_operation}
```

Use a blue point symbol (`#2166AC`) with a white outline. Turn clustering off so
Dashboard selections remain available.

## Part 2 — Web maps

Create two web maps from the same hosted ZCTA layer. This avoids asking one
renderer to explain two policy questions.

### Web map A — Short-Term Response

**Title**

> LA Heat Equity — Short-Term Response

Render unique values from `response_category`:

| Category | Fill | Meaning |
|---|---|---|
| Extreme heat + high vulnerability | `#7F0000` | headline priority |
| Extreme heat | `#D7301F` | severe forecast |
| High vulnerability | `#FC8D59` | structural susceptibility |
| Other short-term snapshot conditions | `#FEE8C8` | comparison |
| No data | `#BDBDBD` | unavailable |

Use white polygon outlines at approximately 0.4 px. Set about 80–85% fill
opacity so boundaries remain legible without competing with the categories.

Popup title:

```text
{place_name} — ZCTA {zcta}
```

Popup order:

1. `response_category`
2. `forecast_date`
3. `heat_risk`
4. `heat_days_ge_3`
5. `svi_pct`
6. `chronic_pct`
7. `POP100`

Format population with separators and percentiles to one decimal. Do not show
the legacy score.

Add cooling centers above the polygons. Save the LA County extent, with Long
Beach and Southeast LA visible without requiring the user to zoom first.

### Web map B — Long-Term Investment

**Title**

> LA Heat Equity — Long-Term Investment

Render unique values from `investment_category`:

| Category | Fill | Meaning |
|---|---|---|
| High harm + high vulnerability + low shade | `#005A32` | headline screen |
| High historical harm + high vulnerability | `#41AB5D` | high structural need |
| Other structural conditions | `#E5F5E0` | comparison |
| No data | `#BDBDBD` | unavailable |

Popup title:

```text
{place_name} — ZCTA {zcta}
```

Popup order:

1. `investment_category`
2. `historical_heat_er`
3. `svi_pct`
4. `vegetation_shade_pct`
5. `chronic_pct`
6. `POP100`

Use the same extent, outlines, basemap, and cooling-center symbol as Web map A.
Consistency makes comparison easier.

### Basemap and labels

Use a light neutral basemap. Avoid satellite imagery under the countywide
choropleths. Keep city/community labels visible but visually quieter than the
priority categories.

## Part 3 — Dashboard

**Title**

> LA County Heat Equity Monitor

**Subtitle**

> July 25 short-term response snapshot, long-term investment, and listed
> cooling resources

### Desktop layout

Use a dark charcoal header (`#252525`) and an off-white body (`#F7F7F5`).

```text
┌─────────────────────────────────────────────────────────────┐
│ Header: title · forecast date · community selector          │
├───────────────────────────────────┬─────────────────────────┤
│ Tabbed maps                       │ Short-term indicator    │
│ [Short-Term Response] [Investment]│ Investment indicator    │
│                                   ├─────────────────────────┤
│                                   │ 7-day forecast chart    │
├───────────────────────────────────┼─────────────────────────┤
│ Cooling-center list               │ Selected-area details   │
└───────────────────────────────────┴─────────────────────────┘
```

ArcGIS Dashboards supports a tabbed view by stacking elements. Add the two map
elements and drag one onto the center of the other. Label the tabs exactly:

- Short-Term Response
- Long-Term Investment

Official layout reference:
<https://doc.arcgis.com/en/dashboards/latest/get-started/dashboard-layout.htm>

### Indicator 1 — Short-term response

- Data: ZCTA hosted layer
- Filter: `response_priority is 1`
- Statistic: sum of `POP100`
- Title: `Residents in areas that met the short-term response rule`
- Number: comma separated, zero decimals
- Caption: `Extreme forecast heat + upper-third vulnerability`
- Color: `#7F0000`

Add a smaller reference statistic or second indicator:

- Statistic: count of `zcta`
- Label: `ZIP-code areas`

### Indicator 2 — Long-term investment

- Data: ZCTA hosted layer
- Filter: `investment_priority is 1`
- Statistic: sum of `POP100`
- Title: `Residents in long-term investment-priority areas`
- Number: comma separated, zero decimals
- Caption: `High historical harm + high vulnerability + low shade`
- Color: `#005A32`

Add a smaller ZCTA-count indicator if space permits.

### Seven-day forecast chart

- Type: serial chart
- Data configuration: categories from fields
- Fields: `heat_day_0` through `heat_day_6`
- Category labels: use actual calendar dates derived from `forecast_date`
- Value label: `CalHeatScore`
- Axis range: 0–4
- Title: `Selected area: seven-day heat forecast`
- No selection text: `Select a ZIP-code area on the Short-Term Response map`

Categories-from-fields charts do not support selection actions. Treat this as a
display target filtered by map selection, not a controller.

### Cooling-center list

- Data: cooling-center point layer
- Title: `Listed cooling centers`
- Primary text: `{site_name}`
- Secondary text: `{address}`
- Description: `{days_hours_of_operation}`
- Sort: `site_name` ascending
- Selection actions: zoom, flash, and show popup on the active map

If available in the authoring interface, apply a spatial or map-extent filter so
the list follows the visible map. Keep an option to reset the Dashboard.

### Selected-area details

Use a Details element sourced from the ZCTA layer. Configure map selection to
filter it. Show:

- place/community;
- ZCTA;
- short-term response category for the July 25 snapshot;
- long-term investment category;
- peak forecast;
- SVI percentile;
- chronic percentile;
- historical harm;
- vegetation shade; and
- population.

Before selection, display:

> Select a ZIP-code area to compare the July 25 snapshot with long-term
> conditions.

### Community selector

Add a category selector in the header:

- field: `place_name`
- display: dropdown
- allow search;
- allow a “None/All communities” option;
- filter both ZCTA operational layers and ZCTA-driven elements.

Do not target the cooling-center list with an attribute filter because the point
layer does not carry `place_name`. Its spatial/extent behavior is separate.

Dashboard selector reference:
<https://doc.arcgis.com/en/dashboards/10.8/create-and-share/selectors.htm>

### Accessibility

On every element’s Accessibility tab, set a useful name similar to its visible
title. Do not use color as the only cue: category names must remain visible in
legends and popups.

Create a mobile view. Minimum mobile order:

1. Short-term response indicator
2. Short-term response map
3. Seven-day forecast
4. Long-term investment indicator
5. Investment map
6. Cooling-center list
7. Selected-area details

## Part 4 — StoryMap

Open `docs/STORYMAP_COPY.md` alongside the builder and paste it section by
section.

Use these tracked assets:

| Story section | Asset |
|---|---|
| Historical validation | `docs/figures/external_validation.png` |
| Long-term shade | `docs/figures/shade_equity.png` |
| Population categories | `docs/figures/equity_priority_population.png` |
| Optional methods detail | `docs/figures/chronic_sensitivity.png` |
| Optional spatial appendix | `docs/figures/spatial_lisa_map.png` |

Do not put every analysis figure in the main narrative. Three figures plus the
Dashboard embed are enough. Move chronic sensitivity and spatial clustering
into an optional methods accordion or omit them from the public story.

Use the Short-Term Response web map early and Long-Term Investment map after the
validation turn. Embed the Dashboard once; repeated full Dashboard embeds make
the story feel like documentation rather than narrative.

## Part 5 — Metadata

For every hosted item, web map, Dashboard, and StoryMap:

- write a one-sentence summary;
- list the six principal sources;
- state the forecast date where relevant;
- link to the repository;
- add `Los Angeles County`, `heat`, `health equity`, `CalHeatScore`, `SVI`,
  `PLACES`, `cooling centers`, and `shade` as tags;
- add descriptive thumbnail and alt text;
- credit LA County, CalEPA, CDC, Census, and UCLA as appropriate.

Do not claim that the map predicts cases, measures cooling-center access, or
estimates the effect of shade interventions.

## Final private-window QA — 15 minutes

Open the public URLs in a signed-out/private browser and verify:

- [ ] StoryMap loads without an organization login.
- [ ] Dashboard loads without an organization login.
- [ ] Both hosted layers are shared at the same level as the applications.
- [ ] Both map tabs render and have correct legends.
- [ ] Short-term and investment population indicators match the pipeline output.
- [ ] Community selector filters both ZCTA views.
- [ ] Clicking a ZCTA updates details and the forecast chart.
- [ ] Cooling-center list shows name, address, and hours.
- [ ] Cooling-center selection zooms or flashes the point.
- [ ] No popup leads with `draft_score`, `resource_gap_pct`, or `dist_m`.
- [ ] Forecast date is visible.
- [ ] Figure captions and image alt text are present.
- [ ] Mobile view is readable without horizontal scrolling.
- [ ] StoryMap links to the Dashboard and repository.
- [ ] Dashboard links back to the StoryMap.

Take three screenshots only after QA:

1. StoryMap opening;
2. Short-Term Response Dashboard;
3. Long-Term Investment Dashboard.

## Two-minute demonstration outline

**0:00–0:20 — question**

> The project began as one heat-equity score. Testing showed that emergency
> response and long-term investment need different maps.

**0:20–0:50 — short-term response**

Show the short-term snapshot map, forecast date, priority population, and one selected
Long Beach/Southeast LA ZCTA.

**0:50–1:15 — validation**

Show the historical-validation figure. Explain that the July 25 forecast weakly
resembles historical harm, while vulnerability and chronic susceptibility
align much more strongly.

**1:15–1:40 — investment**

Switch to the investment map. Explain the historical-harm, vulnerability, and
low-shade screen.

**1:40–1:55 — resources**

Select a cooling center and show its address/hours. State that the list helps
people find resources but distance is not a complete measure of access.

**1:55–2:00 — close**

> The final product is smaller than the research laboratory, but every public
> field survived a documented test.
