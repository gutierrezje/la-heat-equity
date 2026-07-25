# ccphit — LA County Heat Equity Atlas

A reproducible geospatial ETL pipeline that integrates six public datasets across two
geographies onto a common ZIP-code unit, computes an explainable composite heat-equity risk
score, and produces the hosted feature layer behind a public-health Dashboard and StoryMap for
Los Angeles County.

```bash
uv run python -m ccphit.run
```

One command, ~30 seconds, no arguments. Every stage is re-runnable and every output is derived
from source.

## Why this exists

Extreme heat is the deadliest weather hazard in the US, and its burden is not evenly
distributed. The same neighbourhoods with higher chronic disease and poverty also tend to have
hotter microclimates and fewer places to cool off. The pipeline's job is to make that overlap
measurable rather than asserted.

The hard part is not the map — it is that the six sources arrive on **three different
geographies**. Reconciling them onto ZIP Code Tabulation Areas without inventing detail is the
engineering centerpiece; see [Crosswalk](#the-crosswalk) below.

## Sources

| source | provider | native grain | how it joins | scored? |
|---|---|---|---|---|
| CalHeatScore | CalEPA | ZIP, daily 7-day forecast | direct 5-digit match | ✅ heat |
| CDC/ATSDR SVI 2022 | CDC | census tract | population-weighted interpolation | ✅ vulnerability |
| CDC PLACES 2024 | CDC | **ZCTA** | direct | ✅ chronic disease |
| LA County Cooling Centers | LA County | points | distance to nearest | ✅ resource access |
| HRSA Medically Underserved Areas | HRSA | polygons | overlay | context |
| CalEnviroScreen 4.0 | OEHHA/CalEPA | census tract | population-weighted interpolation | context |

Plus reference geography that carries no measurement: Census ZCTA boundaries, the LA County
boundary, and LA County city/community boundaries (for place labels).

**Only SVI requires a manual download.** It is distributed as a File Geodatabase, not an API.
Get `SVI2022_CALIFORNIA_tract.gdb` from
[CDC/ATSDR SVI data downloads](https://www.atsdr.cdc.gov/placeandhealth/svi/data_documentation_download.html)
(California, 2022, census tracts) and unzip it into `data/raw/`. Everything else is fetched over
HTTP with **no API key**.

## Setup

```bash
uv sync
```

Python 3.13, managed by [uv](https://docs.astral.sh/uv/). Then place the SVI geodatabase as
above and run the pipeline.

## Pipeline

Three layers. The directory says how far the data is from its source; the module says what it
produces.

```
sources/    fetch one dataset, normalize, write. No cross-dependencies.
              cooling_centers · calheatscore · svi · places · mua
              calenviroscreen · place_boundaries · boundaries

conform/    bring each native grain onto the ZCTA grain.
              zip_to_zcta      ZIP    -> ZCTA   direct match
              tract_to_zcta    tract  -> ZCTA   population-weighted interpolation
              cooling_access   points -> ZCTA   distance from pop-weighted centroid
              underservice     polys  -> ZCTA   overlay
              place_names      polys  -> ZCTA   containing place of pop-weighted centroid

score.py    the mart: join the spine, compute the composite. Produces zcta_scores.geojson,
            which is what gets published.
```

Resume from any stage:

```bash
uv run python -m ccphit.run --from tract_to_zcta
```

Artifacts written by an older version of the pipeline are rejected on read with an actionable
error rather than failing several stages later — each stage declares the columns it depends on.

## The score

```
draft_score = Σ wᵢ · percentileᵢ        weights sum to 1, output 0–100
```

Four equally weighted pillars, each population-weighted percentile-ranked so all four sit on a
common scale, all pointing the same direction (higher = worse):

**heat** · **social vulnerability** · **chronic disease** · **resource access gap**

Adding or reweighting a pillar is a `config.yml` edit, not a code change:

```yaml
score:
  components:
    chronic:
      columns: [asthma, copd, diabetes, poor_phys_health]
      weight: 0.25
```

A component percentile-ranks each of its columns and averages them, so a single-column pillar
reduces to its own percentile and multi-column pillars need no special case.

> **Read the score as an intensity, not a count.** A high score means conditions are worse
> there, not that more people are affected. Score × population is a different metric.

## The crosswalk

Two sources arrive at census-tract grain and must be reconciled onto ZCTAs. Rather than a naive
centroid join, tract values are apportioned to each tract/ZCTA overlap piece by the **population**
that piece carries, projected to EPSG:3310 for the area maths.

This is not a cosmetic choice, and it is measured rather than asserted:

```bash
uv run python -m ccphit.analysis.crosswalk_validation
```

Area weighting **systematically understates** social vulnerability — population weighting reports
a higher SVI in **221 of 294 ZCTAs (75%)**, sign-test z = 8.6. People concentrate in the more
vulnerable parts of a ZCTA, so weighting by area dilutes toward emptier land. The rejected
centroid join leaves **17 ZCTAs with no value at all**.

## Analysis

```bash
uv run python -m ccphit.analysis.weight_sensitivity     # how much do the weights matter?
uv run python -m ccphit.analysis.crosswalk_validation   # does the weighting choice matter?
```

`weight_sensitivity` draws 20,000 weight vectors from the simplex and re-scores under each. The
result is deliberately unflattering: **no ZCTA is in the top 10 under every weighting**, so no
single ranking is defensible. What *is* defensible is that a stable set of five places appears in
the top 10 under 80–93% of plausible weightings, and that **244 of 282 ZCTAs are top-10 under no
plausible weighting at all**.

## Provenance

Three sources are live services whose contents change, and one — CalHeatScore — serves only the
current 7-day window, so an overwritten pull is gone for good. Every run therefore archives a
dated copy to `data/history/`, and the published layer carries `forecast_date` so it states which
forecast it reflects.

This matters in practice: the cooling-centers layer, documented upstream as a "July 2022
snapshot", churned from 178 to 152 sites between two pulls a month apart, moving the
resource-access measure on 118 of 294 ZCTAs.

## Publishing

```bash
uv run python -m ccphit.publish --dry-run   # validate, change nothing
uv run python -m ccphit.publish             # overwrite the hosted layer
```

An idempotent overwrite that preserves the ArcGIS `itemID`, because the web map, Dashboard, and
StoryMap all reference the layer by id. Credentials come from the environment
(`ARCGIS_PROFILE`, or `ARCGIS_USER`/`ARCGIS_PASSWORD`) and never from config. Creating a new item
is intentionally manual — only the repeatable half is scripted.

## Tests

```bash
uv run pytest
```

The load-bearing one asserts the crosswalk weights by population and not area: two equal-area
tracts with populations 100 and 1 must yield 0.990, where area weighting gives 0.500. The
methodology cannot silently regress.

## Layout

```
src/ccphit/          config · io · weighting · run · score · publish
  sources/           one module per dataset
  conform/           grain reconciliation
  analysis/          weight sensitivity · crosswalk validation
config.yml           endpoints, AOI, score components, crosswalk sources
tests/
data/{raw,interim,processed,history}/   gitignored
proposal/            methodology log and planning docs (gitignored)
```

## Methodology decisions

Every non-obvious choice is logged in `proposal/DECISIONS.md` with its rationale and the
alternative it rejected — the common spatial unit, the ZIP↔ZCTA reconciliation, the three layers
of population weighting, why healthcare access is context rather than a fifth pillar, and why
CalEnviroScreen contributes only its pollution half. That file is the source of truth for the
Dashboard's methods panel and the StoryMap's methodology note.

> Note: `proposal/` is currently gitignored, so the methodology log lives outside version
> control. Worth resolving, since the pipeline's central claim is a documented, reproducible
> method.
