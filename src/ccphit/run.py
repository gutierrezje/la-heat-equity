"""Pipeline orchestrator — runs every stage in dependency order.

    uv run python -m ccphit.run                      # full pipeline
    uv run python -m ccphit.run --from tract_to_zcta  # resume from a stage onward

Three layers, each stage naming the artifact it produces:

    sources/   fetch one external dataset, normalize, write. No cross-dependencies.
      cooling_centers -> cooling_centers
      calheatscore    -> heat_scores
      svi             -> svi_tracts
      places          -> places_zcta       (already ZCTA grain; needs no conform step)
      mua             -> mua_areas         (HRSA medically-underserved area polygons)
      calenviroscreen -> ces_tracts        (environmental burden, tract grain)
      boundaries      -> zcta_bounds

    conform/   bring each native grain onto the ZCTA grain.
      zip_to_zcta    -> zcta_heat_scores        needs zcta_bounds, heat_scores
      tract_to_zcta  -> zcta_svi, zcta_ces      needs zcta_bounds + each configured
                                                tract source (see config `crosswalk`)
      cooling_access -> zcta_nearest_cooling    needs zcta_bounds, cooling_centers, svi_tracts
      underservice   -> zcta_underservice       needs zcta_bounds, mua_areas, svi_tracts
      place_names    -> zcta_place_names        needs zcta_bounds, place_boundaries,
                                                svi_tracts

    score      the mart: join the spine, compute the composite.
      score -> zcta_scores (+ geojson)  needs zcta_heat_scores, zcta_svi,
                                              zcta_nearest_cooling, places_zcta,
                                              zcta_underservice
"""

import subprocess
import sys
import time

STEPS = [
    ("cooling_centers", "ccphit.sources.cooling_centers"),
    ("calheatscore", "ccphit.sources.calheatscore"),
    ("svi", "ccphit.sources.svi"),
    ("places", "ccphit.sources.places"),
    ("mua", "ccphit.sources.mua"),
    ("calenviroscreen", "ccphit.sources.calenviroscreen"),
    ("place_boundaries", "ccphit.sources.place_boundaries"),
    ("boundaries", "ccphit.sources.boundaries"),
    ("zip_to_zcta", "ccphit.conform.zip_to_zcta"),
    ("tract_to_zcta", "ccphit.conform.tract_to_zcta"),
    ("cooling_access", "ccphit.conform.cooling_access"),
    ("underservice", "ccphit.conform.underservice"),
    ("place_names", "ccphit.conform.place_names"),
    ("score", "ccphit.score"),
]


def main(argv: list[str]) -> int:
    steps = STEPS
    if argv[:1] == ["--from"]:
        names = [label for label, _ in STEPS]
        if len(argv) < 2 or argv[1] not in names:
            print(f"usage: --from <stage>  (one of: {', '.join(names)})")
            return 2
        steps = STEPS[names.index(argv[1]):]

    print(f"pipeline: {' -> '.join(label for label, _ in steps)}\n")
    t0 = time.perf_counter()
    for i, (label, module) in enumerate(steps, 1):
        print(f"[{i}/{len(steps)}] {label}  ({module})")
        start = time.perf_counter()
        result = subprocess.run([sys.executable, "-m", module])
        if result.returncode != 0:
            print(f"\n✗ stage '{label}' failed (exit {result.returncode}); stopping.")
            return result.returncode
        print(f"    ✓ {label} in {time.perf_counter() - start:.1f}s\n")

    print(f"✓ pipeline complete in {time.perf_counter() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
