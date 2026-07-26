# Code inventory for the condensed final project

**Prepared:** 2026-07-26 · **Corrected baseline:** `main` @ `baebb0c` · 3,806 lines
of `src/`, 121 tests

Applies D28's retention rule — *"final code should contain only sources used in a figure,
validation check, score, or required interface"* — to every module, by tracing what the
published product actually consumes rather than by reading intent.

**Nothing is deleted here.** D28 gates pruning behind the hosted-layer field migration; this
is the scoping that gate asks for.

---

## Verdict

| tier | lines | share | action |
|---|---:|---:|---|
| **A — production core** | 2,573 | 68% | keep, maintain, keep tested |
| **B — tracked evidence** | 663 | 17% | keep, run on demand |
| **C — backs a tracked decision only** | 307 | 8% | keep for the record |
| **D — exploratory and no longer cited** | 263 | 7% | archive or cut |

These tiers classify analysis code. Source pruning is a separate decision below; a final
line-count target should not be stated until the MUA and CalEnviroScreen decisions are made.

---

## Tier A — production core

Everything the published layer cannot be built without.

**Plumbing** — `config.py` · `io.py` · `weighting.py` · `run.py` (227)

**Sources** (800) — `boundaries` `calheatscore` `cooling_centers` `places` `svi`
`county_heat_outcomes` `shade` `place_boundaries` · plus `mua` `calenviroscreen`, see the
source test below

**Conform** (356) — `zip_to_zcta` `tract_to_zcta` `cooling_access` `underservice` `place_names`

**Mart and delivery** (445) — `score.py` · `product.py` · `publish.py`

**Analysis modules that are actually production** (742) — this is the surprise in the tree:

```
product.py  →  analysis.shade_equity      (shade → ZCTA, used for low_shade_tercile)
product.py  →  analysis.validation        (historical_heat_er, investment_priority)
                 └→ analysis.equity       (imported by validation)
all figures →  analysis.figures           (shared style)
```

`shade_equity`, `validation`, `equity` and `figures` live in `analysis/` but are **import-time
dependencies of the published product**. They cannot be pruned as "analysis." Moving them
could make the package boundary clearer, but that refactor should wait until the StoryMap
and Dashboard are complete.

---

## Tier B — tracked evidence

| module | lines | why it stays |
|---|---:|---|
| `analysis/spatial.py` | 211 | 6 citations + `spatial_lisa_map.png`; backs D27 |
| `analysis/chronic_sensitivity.py` | 139 | 2 citations + `chronic_sensitivity.png`; backs D25 |
| `analysis/crosswalk_validation.py` | 167 | README results and command; defends the tract→ZCTA crosswalk |
| `analysis/weight_sensitivity.py` | 146 | README results and command; tests sensitivity to normative weights |

---

## Tier C — backs a tracked decision, not yet in the report

| module | lines | backs |
|---|---:|---|
| `analysis/candidate_uncertainty.py` | 307 | **D33** — the resource-gap pillar is the drag |

Keep. D33 is the most decision-relevant finding in the repo and this is the only thing that
reproduces it. It should also be cited in the report, which currently states the weaker
heat-based version of the same argument.

---

## Tier D — exploratory and no longer cited

| module | lines | backs | status |
|---|---:|---|---|
| `analysis/structure.py` | 263 | PCA, archetypes → **D1–D19 only** | untracked |

`structure.py` has no citation in `RESEARCH_REPORT.md`, `STORYMAP_COPY.md`, the README,
or `docs/DECISIONS.md`, and is not imported by production.

There is also a records problem independent of this tier. `docs/DECISIONS.md` starts at
**D20**. The original **D1–D19**—the common spatial unit, ZIP↔ZCTA reconciliation,
population-weighted interpolation, and composite design—live only in gitignored
`proposal/DECISIONS.md`.

So the decisions justifying the pipeline's *core design* are untracked, while the tracked
log covers only the audit-era corrections. The still-valid portions of D1–D19 should be
migrated carefully because later entries supersede parts of the early methodology.

`weight_sensitivity` and `candidate_uncertainty` are not substitutes. The first tests how
rankings respond to normative weight choices; the second tests uncertainty in agreement
with an external historical benchmark. Weight sensitivity becomes obsolete only if the
legacy scalar score itself is retired.

---

## Source test against D28

D28 names the leading six as CalHeatScore, SVI, PLACES, historical heat harm, shade, cooling
centers — and marks MUA and CalEnviroScreen "weaker." Tracing actual consumption:

| source | in score formula | in ArcGIS product | tracked evidence | verdict |
|---|:--:|:--:|:--:|---|
| calheatscore | ✅ | ✅ | ✅ | scored pillar |
| svi | ✅ | ✅ | ✅ | scored pillar |
| places | ✅ | ✅ | ✅ | scored pillar |
| cooling_centers | ✅ | ✅ | ✅ | scored pillar |
| county_heat_outcomes | — | ✅ | ✅ | investment view |
| shade | — | ✅ | ✅ | investment view |
| boundaries · place_boundaries | — | ✅ | ✅ | infrastructure |
| **mua** | — | — | — | joined to analytical mart, otherwise unused |
| **calenviroscreen** | — | — | — | joined to analytical mart, otherwise unused |

**CalEnviroScreen fails every limb of D28's test.** Cutting it removes
`sources/calenviroscreen.py` (83), the `ces_tracts` crosswalk entry, and five columns from
the broad `zcta_scores.parquet` analytical mart. Those five columns are **not** in the
public ArcGIS product. It was added for the six-source count; D28's six no longer includes
it.

**MUA is also orphaned, but it is not scored.** `score.py` joins `in_mua` and
`mua_area_share` into the analytical mart as context; neither field appears in
`score.components` or the public export. Either promote MUA to a documented context layer
or remove its source, conform stage, and mart join.

---

## Recommended condensed shape

```
src/ccphit/
├── config.py · io.py · weighting.py · run.py
├── sources/     8 modules  (drop calenviroscreen; resolve mua)
├── conform/     4–5 modules  (drop underservice if mua goes)
├── derive/      ← new home for shade_equity, validation, equity, figures
│                  (production dependencies currently mislabelled as analysis)
├── score.py · product.py · publish.py
└── analysis/    spatial · chronic_sensitivity · candidate_uncertainty
                 · crosswalk_validation
                 (+ weight_sensitivity until the legacy scalar score is retired)
```

## Do these first, in order

1. **Migrate the still-valid parts of D1–D19 from `proposal/` into `docs/`.** Preserve the
   chronological record, but mark claims superseded by D20+ rather than copying
   contradictions as current methodology.
2. **Cut `calenviroscreen` after the ArcGIS migration gate** — it fails all four limbs of
   D28's test and is absent from the public schema.
3. **Decide MUA**: publish and explain it as context, or remove it from the pipeline and
   analytical mart. It is not currently scored.
4. **Retain `weight_sensitivity.py` until the legacy scalar score is retired.** Then remove
   both together rather than claiming candidate uncertainty supersedes it.
5. **Archive or cut `structure.py`** if the PCA/archetype story will not return.
6. **Cite `candidate_uncertainty` (D33) in the report**, which currently makes the weaker
   heat-based version of that argument.
7. **Defer moving production helpers out of `analysis/`** unless package cleanup is worth
   the import churn after the StoryMap and Dashboard are complete. The dependency finding
   is real; the rename is not a product requirement.

Source and public-schema deletions remain gated by D28 behind the Dashboard field
migration. Decision-log repair and report citation are not gated.
