# Evidence-led decision log

This tracked log continues the earlier experimental log in
`proposal/DECISIONS.md`, which remains gitignored. Entries record decisions made
after external evidence and outcome-validation work began. A rejected method is
kept here so it does not quietly return later.

## D20 — Preserve the complete seven-day CalHeatScore forecast

**Decision:** archive `heat_day_0` through `heat_day_6` before deriving
`heat_risk` (peak), `heat_days_ge_3` (duration), and `heat_score_days` (ordinal
severity-days).

**Why:** CalHeatScore serves only the current window. Earlier archives retained
the maximum only, so duration and alternative summaries cannot be reconstructed.
The severity-days sum is descriptive; it is not physical heat dose or health
burden.

**Opus review:** Opus independently implemented this direction in the main
checkout. The branch retained its core design and added rejection of fractional
scores plus mocked pagination, HTTP-error, and service-error tests.

## D21 — Add LA County historical heat harm as validation, never as an input

**Decision:** fetch the Climate-Ready Communities Assessment 2023 tract layer
and population-weight its `heat_tract` excess-ER score onto ZCTAs for external
validation. It must not enter the score it evaluates.

**Result:** rank agreement with historical harm:

| Measure | Spearman rho |
|---|---:|
| Current seven-day peak CalHeatScore | +0.132 |
| Social vulnerability | +0.683 |
| CDC-aligned chronic disease | +0.713 |
| Listed-centre distance | −0.328 |
| Current four-pillar draft index | +0.516 |

Top-decile agreement between the draft index and historical harm is 5 of 28
areas (Jaccard 0.098). This is evidence that current forecast severity and
historical realized harm answer different questions, not that either source is
wrong.

## D22 — Separate emergency response from long-term investment

**Decision:** the final communication should not ask one score to serve both:

- **Current response:** current forecast × susceptibility, with components
  visible and a bivariate priority category as the headline.
- **Long-term investment:** historical harm × vulnerability, with intervention
  layers such as vegetation shade.

**Why:** the current high-vulnerability/extreme-forecast group contains 16 ZCTAs
and 878,241 residents. The historical top-third-harm/high-vulnerability group
contains 68 ZCTAs and 3,359,117 residents. Only 10 areas overlap.

## D23 — Straight-line cooling-center distance fails as a health-risk pillar

**Decision:** retain cooling centers as a facility list and map, but label the
distance measure “straight-line distance to a listed centre,” not access. The
final product should remove it from the composite after the Dashboard migration
is planned.

**Evidence:** no reviewed study establishes a causal health benefit from
proximity or a health-effect distance threshold. Locally, distance correlates
negatively with historical heat harm (`rho=-0.328`) and also reflects density
and polygon size. It does not observe hours, route, travel mode, capacity,
acceptability, or use.

**Rejected:** interpreting a long distance as a demonstrated need for a new
facility. That prescription does not follow from the measure.

## D24 — Accept modeled shade as intervention context

**Decision:** retain LA County/UCLA modeled 2023 3 p.m. shade as an experimental
intervention layer, not a score component.

**Results:** vegetation shade correlates `−0.425` with historical heat harm,
`−0.436` with SVI, and `−0.419` with the CDC-aligned chronic measure. A
transparent screen—top third historical harm, top third vulnerability, bottom
third vegetation shade—identifies 36 ZCTAs and 1,723,130 residents.

**Limitation:** this is observational prioritization. It does not estimate how
many illnesses a planting program would prevent, and vegetation shade at 3 p.m.
is not identical to pedestrian thermal comfort.

## D25 — Use the CDC Heat & Health Index-aligned chronic condition set

**Decision:** replace asthma/COPD/diabetes/poor physical health with CHD,
obesity, diabetes, COPD, asthma, and poor mental health, averaged as
population-weighted percentiles.

**Experiment:**

| Design | rho with SVI | rho with historical harm |
|---|---:|---:|
| Former four-condition mean | .787 | .704 |
| CDC-aligned continuous mean | .769 | .713 |
| CDC-aligned local-tertile flags | .642 | .558 |

The continuous CDC-aligned set modestly improves outcome agreement and modestly
reduces overlap with SVI. The local-tertile flag experiment reduces overlap
more, but loses too much outcome agreement and does not reproduce CDC's national
cut points.

## D26 — Retire score × population as “burden”

**Decision:** remove the concentration curve and `draft_score * POP100`
analysis. Replace it with population counts inside explicitly defined heat ×
vulnerability categories.

**Why:** a weighted sum of percentile ranks is ordinal. Multiplying it by
population does not produce cases, people harmed, or units of risk. Population
counts remain valid after a category rule is declared.

## D27 — Use mainland queen contiguity and FDR control

**Decision:** evaluate contiguous mainland ZCTAs with queen adjacency, report
Catalina separately, and adjust Local Moran p-values using
Benjamini-Hochberg false-discovery-rate control.

**Result:** global Moran's I remains strong (`0.596`, permutation `p=.001`), but
local results shrink from 103 unadjusted KNN flags to 63 corrected mainland
flags: 25 high-high, 37 low-low, and one low-high. Cerritos and Claremont are no
longer significant. The earlier “municipal islands” narrative is rejected.

## D28 — Expand during discovery; prune for the final product

**Decision:** discovery may exceed six sources. At all times retain at least two
assignment-required sources; PLACES and SVI satisfy that constraint.

The current laboratory has eight substantive sources. The leading six-source
final candidate is CalHeatScore, SVI, PLACES, LA County historical heat harm,
modeled shade, and cooling centers. Cooling centers satisfy the promised
facility-list function, not a score pillar. MUA and CalEnviroScreen remain useful
experiments but are weaker for the final response/investment distinction.

**Pruning gate:** do not delete sources until the hosted-layer and Dashboard
field migration is scoped. Final code should contain only sources used in a
figure, validation check, score, or required interface.

## D29 — Do not select a score solely by historical correlation

**Experiment:**

| Candidate | rho with historical harm |
|---|---:|
| Current four-pillar draft | .516 |
| Heat + SVI + chronic, equal thirds | .680 |
| 50% heat + 25% SVI + 25% chronic | .550 |
| Susceptibility only | .737 |

Removing facility distance improves historical agreement. Susceptibility alone
aligns best because the criterion is historical harm, but it cannot respond to a
changing forecast. Therefore historical correlation is a diagnostic, not an
automatic weighting rule.

**Final-product recommendation:** lead with the bivariate current-response
category, publish heat/SVI/chronic components, and keep any scalar response
index secondary. Remove facility distance from its formula in a focused
Dashboard-migration PR.
