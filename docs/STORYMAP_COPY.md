# Paste-ready StoryMap copy

This is the public-facing version of the research report. Replace bracketed
snapshot values after the final pipeline run. Keep the technical detail in the
last section rather than interrupting the narrative.

## Cover

**Title**

> Two maps for one hotter county

**Subtitle**

> Where Los Angeles County should respond during this week’s heat—and where
> longer-term investment may matter most

**Optional kicker**

> LA County Heat Equity Atlas

**Cover image direction**

Use a human-scale, properly licensed photograph from Long Beach or Southeast
Los Angeles showing people moving through an exposed street, bus stop, school
route, or commercial corridor. Prefer everyday heat exposure over wildfire,
thermometer, or generic skyline imagery.

**Cover alt text**

> People traveling along a sun-exposed street in Los Angeles County during hot
> weather.

## Opening

### Heat is one hazard, but it creates two policy questions

Extreme heat does not affect every community in the same way. The weather
changes from week to week, while chronic illness, social vulnerability, the
built environment, and access to protective resources change much more slowly.

That distinction matters. Emergency managers need to know where the current
forecast overlaps with vulnerable populations. Long-term planners need to know
where heat has repeatedly produced harm and where protective conditions such as
vegetation shade are scarce.

This project originally combined those questions in one score. Local outcome
data showed that the result was easier to calculate than to interpret. The
atlas now presents two transparent views instead.

**Transition sentence**

> First: where are current conditions most concerning?

## Section 1 — Current response

### Where extreme forecast heat meets high vulnerability

For the forecast issued **[FORECAST DATE]**, the current-response map highlights
ZIP-code areas that meet two conditions:

1. a peak seven-day CalHeatScore of 4, indicating extreme forecast heat-health
   risk; and
2. social vulnerability in the upper third of LA County ZIP-code areas.

In this snapshot, **[CURRENT ZCTA COUNT] ZIP-code areas** containing
**[CURRENT POPULATION] residents** meet both conditions.

These are residents of areas that meet a screening rule. The number is not a
forecast of illnesses, emergency-room visits, or deaths.

**Embed**

Embed the Dashboard with the Current Response map visible.

**Dashboard instruction text**

> Select a ZIP-code area to see its seven-day forecast, social vulnerability,
> and chronic-health context. Use the cooling-center list to view currently
> listed facilities and operating information.

### A Long Beach anchor

Long Beach ZIP-code area **90813** is an important example because high social
vulnerability and chronic-health susceptibility overlap there with severe
forecast conditions. It also appears in the long-term shade screen described
below.

This does not mean every resident experiences the same risk. ZIP-code areas are
screening geographies, not neighborhoods with uniform conditions.

**Suggested visual**

Use a map action or map tour stop centered on 90813. Add a locally relevant,
properly licensed street-level image if one is available.

## Section 2 — Why one forecast is not the whole story

### This week’s forecast and historical harm are different maps

LA County’s Climate-Ready Communities Assessment includes a tract-level heat
measure based on excess emergency-room visits. After translating it to the
project’s ZIP-code areas, the current seven-day forecast has only **0.13 rank
agreement** with historical heat harm.

Rank agreement asks a simple question: do places near the top of one measure
also tend to appear near the top of another? Here, the answer is usually no.

By comparison:

- social vulnerability has **0.68** rank agreement with historical harm; and
- chronic-disease susceptibility has **0.71** rank agreement.

> Weather helps show where danger is imminent. Vulnerability helps explain
> where heat has historically produced emergency-room harm.

**Figure**

Upload and insert `docs/figures/external_validation.png`.

**Figure caption**

> Current forecast severity only weakly resembles the historical harm map.
> Social vulnerability and chronic-health susceptibility align much more
> strongly with observed historical harm.

**Figure alt text**

> Three-panel chart comparing historical heat-related emergency-room harm with
> current CalHeatScore, social vulnerability, chronic disease, the draft index,
> and cooling-center distance.

## Section 3 — Long-term investment

### Where historical harm, vulnerability, and low shade coincide

The long-term investment screen highlights ZIP-code areas with:

1. historical heat harm in the upper third;
2. social vulnerability in the upper third; and
3. modeled vegetation shade in the lower third.

The screen identifies **[INVESTMENT ZCTA COUNT] ZIP-code areas** containing
**[INVESTMENT POPULATION] residents**.

Vegetation shade is lower where historical harm, vulnerability, and chronic
susceptibility are higher. That makes shade useful for identifying places where
more detailed planning should begin.

It does not prove how much a planting project would reduce illness. The shade
layer models one summer day at 3 p.m.; it is not a complete measure of
pedestrian thermal comfort, tree health, feasibility, ownership, water needs,
or maintenance capacity.

**Map**

Switch the embedded Dashboard or web map to Long-Term Investment.

**Figure**

Upload and insert `docs/figures/shade_equity.png`.

**Figure caption**

> Modeled vegetation shade is lower in ZIP-code areas with greater structural
> heat-health need. The map highlights areas meeting all three declared
> investment-screen conditions.

**Figure alt text**

> Charts showing vegetation shade declining as vulnerability rises, negative
> rank relationships between shade and structural need, and a map of the
> long-term investment screen.

## Section 4 — Find resources

### Cooling centers are useful locations, not a complete measure of access

The resource map lists currently available cooling-center names, addresses, and
reported operating hours. Check the facility information before traveling
because the county’s live list changes over time.

Straight-line distance to a listed center is not the same as access. It does
not measure transit routes, walking conditions, capacity, disability access,
awareness, acceptability, or whether a facility is open during a particular
heat event.

The local validation reinforces that limitation: areas farther from listed
centers had lower historical heat harm. This likely reflects where facilities
have been placed and the geography of urban density; it is not evidence that
distance is protective.

> Use the facility layer to find and verify resources. Do not use it alone to
> decide where a new center should be built.

**Embed**

Show the cooling-center point layer and list. Make `site_name`, `address`, and
`days_hours_of_operation` visible.

## Section 5 — What changed during the research

### Several plausible ideas did not survive testing

- Cooling-center distance was removed from the recommended risk formula.
- Multiplying an ordinal score by population was retired as a false “burden”
  measure.
- A local spatial-outlier story disappeared after correcting the neighbor
  graph and controlling false discoveries.
- A more complicated chronic-disease flag method performed worse than a simple
  continuous measure.
- One score was replaced by separate response and investment views.

These are not failed deliverables. They are evidence that the final product was
allowed to change when its assumptions were tested.

**Optional figure**

Use `docs/figures/equity_priority_population.png`.

**Caption**

> Population is counted after an understandable category is declared. Index
> points are not treated as illnesses or units of burden.

## Methods and limitations

### Methods in plain language

The pipeline combines six principal public sources:

- CalHeatScore;
- CDC/ATSDR Social Vulnerability Index;
- CDC PLACES;
- LA County historical excess-emergency-room heat harm;
- LA County/UCLA modeled shade; and
- LA County cooling centers.

The sources begin as ZIP records, census tracts, census block groups, and
points. They are reconciled onto Census ZIP Code Tabulation Areas. Tract values
are translated using population-weighted areal interpolation; shade is averaged
according to the ground area overlapping each ZIP-code area.

The analysis uses percentile ranks, thirds, rank correlations, population
counts after declared categories, and standard spatial-clustering diagnostics.
These methods compare and screen places. They do not establish causal effects
or predict future case counts.

### Limitations

- CalHeatScore is a current seven-day forecast and can change with every run.
- PLACES values are modeled small-area estimates.
- SVI and PLACES are not statistically independent; both incorporate
  demographic information.
- Crosswalks approximate how populations are distributed within source
  geographies.
- Historical harm and modeled shade describe published 2023 analyses.
- ZIP-code areas contain meaningful variation within their boundaries.
- Cooling-center listings and hours can change.
- Shade prioritization identifies places for closer investigation, not the
  health effect of a specific intervention.

### Source and methods links

- Project methods: link to `docs/RESEARCH_REPORT.md` in the repository.
- Reproducible code: link to the repository homepage.
- CalHeatScore: <https://calheatscore.calepa.ca.gov/>
- LA County historical heat assessment:
  <https://www.arcgis.com/home/item.html?id=fefe544f3ddb413a82ebb11e2a42f974>
- LA County/UCLA modeled shade:
  <https://www.arcgis.com/home/item.html?id=53f78d9d6fcf43678a3272de2a15720c>
- CDC PLACES: <https://www.cdc.gov/places/>
- CDC/ATSDR SVI: <https://www.atsdr.cdc.gov/place-health/php/svi/>

## Closing

### Better decisions begin with asking which decision the map supports

A current forecast can guide near-term response. Historical health outcomes and
structural conditions can guide longer-term investigation. Cooling-center
locations can help people find a listed resource.

None of those maps can do the others’ job by itself.

The most defensible heat-equity product is therefore not a universal ranking.
It is a set of transparent views that state what was measured, what decision
each view can support, and what the data cannot tell us.

