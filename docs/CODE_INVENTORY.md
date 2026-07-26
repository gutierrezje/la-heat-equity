# Code inventory for the condensed final project

**Prepared:** 2026-07-26 · **Baseline:** `main` @ `1e797f1` · 3,806 lines of `src/`, 118 tests

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
| **B — cited evidence** | 350 | 9% | keep, run on demand |
| **C — backs a tracked decision only** | 307 | 8% | keep for the record |
| **D — backs nothing tracked** | 576 | 15% | **cut or migrate its decisions** |

The condensed project is roughly **3,230 lines (85%)**. The genuine cut is Tier D.

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
dependencies of the published product**. They cannot be pruned as "analysis," and they should be
moved out of `analysis/` so the boundary reflects reality.

---

## Tier B — evidence the final report cites

| module | lines | why it stays |
|---|---:|---|
| `analysis/spatial.py` | 211 | 6 citations + `spatial_lisa_map.png`; backs D27 |
| `analysis/chronic_sensitivity.py` | 139 | 2 citations + `chronic_sensitivity.png`; backs D25 |

---

## Tier C — backs a tracked decision, not yet in the report

| module | lines | backs |
|---|---:|---|
| `analysis/candidate_uncertainty.py` | 307 | **D33** — the resource-gap pillar is the drag |

Keep. D33 is the most decision-relevant finding in the repo and this is the only thing that
reproduces it. It should also be cited in the report, which currently states the weaker
heat-based version of the same argument.

---

## Tier D — backs nothing in the tracked record

| module | lines | backs | status |
|---|---:|---|---|
| `analysis/structure.py` | 263 | PCA, archetypes → **D1–D19 only** | untracked |
| `analysis/crosswalk_validation.py` | 167 | crosswalk defence → **D19** | untracked |
| `analysis/weight_sensitivity.py` | 146 | rank stability → **D18** | untracked |

Zero citations in `RESEARCH_REPORT.md` or `STORYMAP_COPY.md`; zero references in
`docs/DECISIONS.md`; none imported by production.

**The reason is a records problem, not a quality problem.** `docs/DECISIONS.md` is a fresh log
starting at **D20**. The original **D1–D19** — the common spatial unit, the ZIP↔ZCTA
reconciliation, population-weighted interpolation, the composite design — live **only in
gitignored `proposal/DECISIONS.md`**.

So the decisions justifying the pipeline's *core design* are untracked, while the tracked log
covers only the audit-era corrections. Two consequences:

1. `weight_sensitivity` is genuinely **superseded**. `candidate_uncertainty` answers the same
   question against an *external* benchmark instead of the score's own components. Cut it.
2. `structure` and `crosswalk_validation` are **not** superseded — the crosswalk is still the
   project's engineering centrepiece, and it is currently defended by an untracked document and
   an uncited module. **Migrate D5/D8/D19 into `docs/`, or the crosswalk claim has no tracked
   justification.**

---

## Source test against D28

D28 names the leading six as CalHeatScore, SVI, PLACES, historical heat harm, shade, cooling
centers — and marks MUA and CalEnviroScreen "weaker." Tracing actual consumption:

| source | in score | in product | in docs | verdict |
|---|:--:|:--:|--:|---|
| calheatscore | ✅ | ✅ | 10 | scored pillar |
| svi | ✅ | ✅ | 4 | scored pillar |
| places | ✅ | ✅ | 8 | scored pillar |
| cooling_centers | ✅ | ✅ | 11 | scored pillar |
| county_heat_outcomes | — | ✅ | 3 | investment view |
| shade | — | ✅ | 0 | investment view |
| boundaries · place_boundaries | ✅ | ✅ | 8 / 5 | infrastructure |
| **mua** | ✅ | ❌ | 0 | **scored but not published or discussed** |
| **calenviroscreen** | ❌ | ❌ | 0 | **no downstream use at all** |

**CalEnviroScreen fails every limb of D28's test.** Cutting it removes `sources/calenviroscreen.py`
(83), the `ces_tracts` crosswalk entry, and five product columns. It was added for the
six-source count; D28's six no longer includes it.

**MUA is the awkward one.** It is a *scored* input — `in_mua` appears in `score.py` — yet appears
in no figure, no report section, and is absent from the product. Either promote it to the
published layer or drop it from the score; scoring an input nobody can see is the worst of both.

*(`shade` shows 0 doc mentions because the report references it as "shade" prose and
`shade_equity.png`; it is genuinely used.)*

---

## Recommended condensed shape

```
src/ccphit/
├── config.py · io.py · weighting.py · run.py
├── sources/     8 modules  (drop calenviroscreen; resolve mua)
├── conform/     5 modules  (drop underservice if mua goes)
├── derive/      ← new home for shade_equity, validation, equity, figures
│                  (production dependencies currently mislabelled as analysis)
├── score.py · product.py · publish.py
└── analysis/    spatial · chronic_sensitivity · candidate_uncertainty
                 (+ structure, crosswalk_validation *if* D5/D8/D19 are migrated)
```

## Do these first, in order

1. **Migrate D1–D19 from `proposal/` into `docs/`.** Everything else in Tier D depends on this
   answer, and the repo's central reproducibility claim currently rests on untracked files.
2. **Cut `weight_sensitivity.py`** — superseded by `candidate_uncertainty.py`.
3. **Cut `calenviroscreen`** — fails all four limbs of D28's test.
4. **Decide MUA**: publish it or unscore it.
5. **Move `shade_equity`, `validation`, `equity`, `figures` out of `analysis/`** so the package
   boundary matches the import graph.
6. **Cite `candidate_uncertainty` (D33) in the report**, which currently makes the weaker
   heat-based version of that argument.

Steps 2–5 are gated by D28 behind the Dashboard field migration. Step 1 is not gated and should
happen regardless.
