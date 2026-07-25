# ccphit — LA County Heat Equity Atlas

A reproducible geospatial research pipeline that integrates public heat, health,
vulnerability, outcome, facility, and intervention data onto a common ZIP-code unit. It
produces the hosted feature layer behind a public-health Dashboard and StoryMap for Los
Angeles County and keeps validation sources separate from production score inputs.

```bash
uv run python -m ccphit.run
```

One command, ~30 seconds, no arguments. Every stage is re-runnable and every output is derived
from source.

## Why this exists

Extreme heat is the deadliest weather hazard in the US, and its harm is not evenly
distributed. Current forecast severity, historical emergency-room harm, underlying
susceptibility, and protective infrastructure are related but distinct. The pipeline's job is
to measure those relationships rather than assume they identify the same places.

The hard part is not the map — it is that the sources arrive on **several different
geographies**. Reconciling them onto ZIP Code Tabulation Areas without inventing detail is the
engineering centerpiece; see [Crosswalk](#the-crosswalk) below.

## Sources

| source | provider | native grain | how it joins | scored? |
|---|---|---|---|---|
| CalHeatScore | CalEPA | ZIP, daily 7-day forecast | direct 5-digit match | ✅ heat |
| CDC/ATSDR SVI 2022 | CDC | census tract | population-weighted interpolation | ✅ vulnerability |
| CDC PLACES 2024 | CDC | **ZCTA** | direct | ✅ chronic disease |
| LA County Cooling Centers | LA County | points | distance to nearest | ⚠️ draft pillar; facility context |
| HRSA Medically Underserved Areas | HRSA | polygons | overlay | context |
| CalEnviroScreen 4.0 | OEHHA/CalEPA | census tract | population-weighted interpolation | context |
| LA County historical heat harm | LA County/UCLA | census tract | population-weighted interpolation | external validation |
| Modeled 3 p.m. shade | LA County/UCLA | census block group | area-weighted interpolation | intervention experiment |

Plus reference geography that carries no measurement: Census ZCTA boundaries, the LA County
boundary, and LA County city/community boundaries (for place labels).

The laboratory intentionally exceeds six sources while alternatives are tested. PLACES and SVI
remain two assignment-required sources. The evidence-led final candidate is documented in
[`docs/RESEARCH_REPORT.md`](docs/RESEARCH_REPORT.md).

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
              calenviroscreen · county_heat_outcomes · shade
              place_boundaries · boundaries

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

The currently published draft has four equally weighted pillars, each population-weighted
percentile-ranked onto a common scale:

**heat** · **social vulnerability** · **chronic disease** · **listed-centre distance**

External validation found that listed-centre distance correlates negatively with historical
heat harm and does not observe true access. It remains in the draft for Dashboard compatibility;
the recommendation is to remove it from the formula and keep cooling centers as a searchable
facility layer. See decisions D23 and D29.

Adding or reweighting a pillar is a `config.yml` edit, not a code change:

```yaml
score:
  components:
    chronic:
      columns: [chd, obesity, diabetes, copd, asthma, poor_mental_health]
      weight: 0.25
```

A component percentile-ranks each of its columns and averages them, so a single-column pillar
reduces to its own percentile and multi-column pillars need no special case.

> **Read the score as an index, not a count or health effect.** It does not estimate
> people harmed, cases, or attributable risk. The former score × population “burden”
> analysis has been retired.

## The crosswalk

Two sources arrive at census-tract grain and must be reconciled onto ZCTAs. Rather than a naive
centroid join, tract values are apportioned to each tract/ZCTA overlap piece by the **population**
that piece carries, projected to EPSG:3310 for the area maths.

This is not a cosmetic choice, and it is measured rather than asserted:

```bash
uv run python -m ccphit.analysis.crosswalk_validation
```

Area weighting **systematically understates** social vulnerability — population weighting reports
a higher SVI in **221 of 294 ZCTAs (75%)**, sign-test z = 8.6. This shows that more-populous
tract pieces carry different values than less-populous pieces; it does not reveal where people
live inside a tract. Population is apportioned uniformly within each tract overlap, an explicit
approximation. The rejected centroid join leaves **17 ZCTAs with no value at all**.

## Analysis

```bash
uv run python -m ccphit.analysis.weight_sensitivity     # how much do the weights matter?
uv run python -m ccphit.analysis.crosswalk_validation   # does the weighting choice matter?
uv run python -m ccphit.analysis.validation             # forecast vs historical ER harm
uv run python -m ccphit.analysis.chronic_sensitivity    # condition-set experiment
uv run python -m ccphit.analysis.shade_equity           # intervention-oriented shade screen
uv run python -m ccphit.analysis.equity                 # category population, not pseudo-burden
uv run python -m ccphit.analysis.spatial                # corrected contiguity + FDR
```

`weight_sensitivity` draws 20,000 weight vectors from the simplex and re-scores under each.
No ZCTA is in the top 10 under every sampled weighting. This is a stress test over a
deliberately broad choice space, not proof that ranking is impossible for every decision.
The primary report now uses declared bivariate categories and publishes the components.

## Provenance

Several sources are live services whose contents change, and CalHeatScore serves only the
current seven-day window. Every run archives dated snapshots where needed. CalHeatScore archives
now retain all seven daily values plus peak, high-risk-day count, severity-days, and declared
method version; earlier maximum-only archives cannot be repaired.

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
  analysis/          sensitivity · external validation · shade · equity · spatial
config.yml           endpoints, AOI, score components, crosswalk sources
tests/
docs/                tracked research report · decisions · selected figures
data/{raw,interim,processed,history}/   gitignored
proposal/            methodology log and planning docs (gitignored)
```

## Methodology decisions

Earlier choices remain in the experimental `proposal/DECISIONS.md`. Evidence-led decisions from
the external validation onward are version controlled in
[`docs/DECISIONS.md`](docs/DECISIONS.md), including failed experiments and pruning gates.
