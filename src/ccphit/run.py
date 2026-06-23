"""Pipeline orchestrator — runs every stage in dependency order.

    uv run python -m ccphit.run                # full pipeline
    uv run python -m ccphit.run --from zcta     # resume from a stage onward

Dependency notes (what each stage produces / needs):
    cooling       -> cooling_centers                      (independent)
    calheatscore  -> heat_scores                          (independent)
    svi           -> svi_tracts                           (independent)
    zcta          -> zcta_bounds, zcta_heat_scores        needs heat_scores
    crosswalk     -> zcta_svi                             needs svi_tracts, zcta_bounds
    nearest       -> zcta_nearest_cooling                 needs zcta_bounds, cooling_centers, svi_tracts
    score         -> zcta_scores (+ geojson)              needs zcta_heat_scores, zcta_svi, zcta_nearest_cooling
"""

import subprocess
import sys
import time

STEPS = [
    ("cooling", "ccphit.sources.cooling"),
    ("calheatscore", "ccphit.sources.calheatscore"),
    ("svi", "ccphit.sources.svi"),
    ("zcta", "ccphit.sources.zcta"),
    ("crosswalk", "ccphit.transform.crosswalk"),
    ("nearest", "ccphit.transform.nearest"),
    ("score", "ccphit.transform.score"),
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
