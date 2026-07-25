# Research and pipeline audit backlog

This tracked backlog preserves the still-open findings from the independent
Opus audit performed against commit `92d6acc` on 2026-07-25. Its four urgent
plans have since been completed:

- public claims were corrected in `docs/RESEARCH_REPORT.md`;
- mainland queen contiguity and false-discovery-rate control replaced the
  exploratory KNN local analysis;
- score × population pseudo-burden was replaced by population counts after
  declared category rules; and
- the complete seven-day CalHeatScore forecast is now validated and archived.

The older uncommitted implementations and `TODO` plans are not production
inputs. The items below are the useful work that remains.

## Priority 1 — trustworthy ArcGIS refreshes

### Add a run manifest

`--from` currently checks artifact columns but cannot prove that inputs came
from compatible runs. A manifest should record:

- forecast date;
- observation timestamp for each live source;
- declared method versions;
- configuration hash; and
- artifact hashes.

Before publishing, reject mixed or incompatible source vintages. This matters
more than further refinement of the score because the public product must state
honestly what date each view represents.

### Reject mixed forecast dates

The publisher currently chooses the latest date when rows contain multiple
forecast dates. A public layer should contain exactly one forecast issue date.
Validation should fail before authentication if that invariant is violated.

### Prevent same-day archive collisions

History filenames use a logical date. Two materially different pulls observed
on the same date can overwrite one another. Retain the readable logical date,
but distinguish same-day content with an observation timestamp or content
hash.

## Priority 2 — source reliability

### Harden cooling-center ingestion

Add a request timeout, response-schema checks, mocked pagination tests, and
clear service-error handling. Preserve names, addresses, and operating hours
because this source supports the facility list rather than a risk pillar.

### Guard PLACES and MUA completeness

PLACES currently depends on a fixed response limit and MUA on a single request.
Paginate or assert service completeness so upstream truncation cannot silently
look like valid coverage.

### Resolve configuration paths predictably

`load_config()` resolves `config.yml` from the current working directory. Make
the default repository/package-relative or support an explicit config path so
installed commands do not fail outside the project root.

## Priority 3 — measured methodological refinements

### Inventory geographic vintages

The 2010 ZCTA spine is combined with newer tract and ZCTA-era products. Before
changing the spine, compare the candidate vintage on coverage, direct joins,
population totals, crosswalk values, priority membership, and ArcGIS geometry
size. Do not make an incidental endpoint swap.

### Make nearest-center ties deterministic

Equal-distance facilities can produce multiple nearest-join rows. The distance
is correct, but the retained name/address may depend on row order. Sort by a
stable identifier and retain a tie count, or keep all tied facilities in the
point-layer interface.

### Describe centroid approximations precisely

The population-weighted centroid apportions tract population uniformly across
tract/ZCTA overlap pieces. It is an area-apportioned tract-population centroid,
not an observed resident location. Keep this limitation in technical methods if
the distance field remains available during Dashboard migration.

## Product positioning

Do not claim the project is the first LA heat dashboard or bivariate heat
index. Its contribution is a reproducible current-forecast ZCTA synthesis,
explicit separation of response and investment decisions, transparent
component views, local outcome validation, and an auditable critique of methods
that did not survive testing.

Redlining remains out of the final product. If revisited, describe its
association with present heat as mediated through current land cover and
inequality; do not claim an independently identified causal effect from this
project.

## Promotion rule

Promote an item from this backlog only when it has:

1. a specific user or publication risk;
2. a bounded implementation plan;
3. expected files and verification;
4. a measurement gate where the result could change the decision; and
5. a plain-language implication for the StoryMap or Dashboard.

Do not add a source or method merely to make the project appear more complex.
