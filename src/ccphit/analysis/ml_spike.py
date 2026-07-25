"""PROTOTYPE — spatially honest ML test for historical heat-harm prediction.

One command:

    uv run python -m ccphit.analysis.ml_spike

This is deliberately not a production score. It tests whether nonlinear models
generalize to held-out parts of LA County better than transparent baselines.
"""

from pathlib import Path
import time

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from esda.moran import Moran
from libpysal.weights import Queen
from scipy.stats import spearmanr
from sklearn.base import clone
from sklearn.compose import TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, RepeatedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ccphit.config import CRS_M, load_config
from ccphit.io import read_processed

SEED = 20260725
N_SPLITS = 5
N_REPEATS = 8
OUT = Path("data/ml_spike")
TARGET = "historical_heat_er"

FEATURE_GROUPS = {
    "SVI themes": [
        "svi_socioeconomic",
        "svi_household",
        "svi_minority",
        "svi_housing_transport",
    ],
    "chronic conditions": [
        "chd",
        "obesity",
        "diabetes",
        "copd",
        "asthma",
        "poor_mental_health",
    ],
    "modeled shade": ["vegetation_shade_pct", "building_shade_pct"],
    "pollution context": [
        "pollution_pct",
        "pm25",
        "diesel_pm",
        "ozone",
        "tox_release",
    ],
    "population / urban form": ["log_population", "population_density_km2"],
}
FEATURES = [column for columns in FEATURE_GROUPS.values() for column in columns]


def models() -> dict:
    """Fixed, conservative candidates: no tuning against the held-out folds."""
    return {
        "mean baseline": DummyRegressor(strategy="mean"),
        "ridge": make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            Ridge(alpha=10.0),
        ),
        "robust linear": make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            HuberRegressor(epsilon=1.5, alpha=0.1, max_iter=2_000),
        ),
        "shallow boosting": make_pipeline(
            SimpleImputer(strategy="median"),
            HistGradientBoostingRegressor(
                learning_rate=0.04,
                max_iter=150,
                max_leaf_nodes=7,
                min_samples_leaf=20,
                l2_regularization=5.0,
                random_state=SEED,
            ),
        ),
        "extra trees": make_pipeline(
            SimpleImputer(strategy="median"),
            ExtraTreesRegressor(
                n_estimators=200,
                max_depth=5,
                min_samples_leaf=8,
                max_features=0.7,
                n_jobs=-1,
                random_state=SEED,
            ),
        ),
    }


def prepare(config: dict) -> gpd.GeoDataFrame:
    d = read_processed(
        "zcta_product",
        config,
        geo=True,
        require=["zcta", "POP100", TARGET, *FEATURES[:-2]],
    ).to_crs(CRS_M)
    d = d.copy()
    d["log_population"] = np.log1p(d["POP100"])
    d["population_density_km2"] = d["POP100"] / (d.geometry.area / 1_000_000)
    return d.reset_index(drop=True)


def geographic_splits(d: gpd.GeoDataFrame):
    """Eight rotated five-band partitions; every test fold is spatially held out."""
    centers = np.column_stack([d.geometry.centroid.x, d.geometry.centroid.y])
    centers = StandardScaler().fit_transform(centers)
    for repeat in range(N_REPEATS):
        angle = repeat * np.pi / N_REPEATS
        axis = np.array([np.cos(angle), np.sin(angle)])
        projection = centers @ axis
        # Equal-count spatial bands prevent one large rural region from dominating
        # a fold while rotation makes the extrapolation direction a real stress test.
        groups = pd.qcut(
            pd.Series(projection).rank(method="first"),
            N_SPLITS,
            labels=False,
        ).to_numpy()
        splitter = GroupKFold(n_splits=N_SPLITS)
        for fold, (train, test) in enumerate(splitter.split(d, groups=groups)):
            yield repeat, fold, train, test, groups


def random_splits(d: gpd.GeoDataFrame):
    splitter = RepeatedKFold(
        n_splits=N_SPLITS,
        n_repeats=N_REPEATS,
        random_state=SEED,
    )
    for sequence, (train, test) in enumerate(splitter.split(d)):
        yield sequence // N_SPLITS, sequence % N_SPLITS, train, test, None


def top_third_recall(actual: np.ndarray, predicted: np.ndarray) -> float:
    n = max(1, len(actual) // 3)
    actual_top = set(np.argsort(actual)[-n:])
    predicted_top = set(np.argsort(predicted)[-n:])
    return len(actual_top & predicted_top) / n


def evaluate(d, split_name, split_iterator, log_target=False):
    X = d[FEATURES]
    y = d[TARGET].to_numpy()
    rows = []
    prediction_rows = []
    for repeat, fold, train, test, groups in split_iterator:
        for name, estimator in models().items():
            model = clone(estimator)
            if log_target and name != "mean baseline":
                model = TransformedTargetRegressor(
                    regressor=model,
                    func=np.log1p,
                    inverse_func=np.expm1,
                    check_inverse=False,
                )
            started = time.perf_counter()
            model.fit(X.iloc[train], y[train])
            pred = np.maximum(0, model.predict(X.iloc[test]))
            elapsed = time.perf_counter() - started
            rho = (
                spearmanr(y[test], pred).statistic
                if np.unique(pred).size > 1
                else np.nan
            )
            rows.append(
                {
                    "split": split_name,
                    "target_scale": "log1p" if log_target else "raw",
                    "model": name,
                    "repeat": repeat,
                    "fold": fold,
                    "n_train": len(train),
                    "n_test": len(test),
                    "mae": mean_absolute_error(y[test], pred),
                    "rmse": mean_squared_error(y[test], pred) ** 0.5,
                    "r2": r2_score(y[test], pred),
                    "spearman": rho,
                    "top_third_recall": top_third_recall(y[test], pred),
                    "fit_seconds": elapsed,
                }
            )
            for index, observed, estimate in zip(test, y[test], pred):
                prediction_rows.append(
                    {
                        "split": split_name,
                        "repeat": repeat,
                        "fold": fold,
                        "row": index,
                        "zcta": d.iloc[index]["zcta"],
                        "model": name,
                        "target_scale": "log1p" if log_target else "raw",
                        "observed": observed,
                        "predicted": estimate,
                        "region": int(groups[index]) if groups is not None else pd.NA,
                    }
                )
    return pd.DataFrame(rows), pd.DataFrame(prediction_rows)


def pooled_metrics(predictions):
    """One countywide out-of-fold score per repeat; every ZCTA contributes once."""
    rows = []
    keys = ["split", "target_scale", "model", "repeat"]
    for key, values in predictions.groupby(keys):
        actual = values["observed"].to_numpy()
        predicted = values["predicted"].to_numpy()
        rows.append(
            {
                **dict(zip(keys, key)),
                "n": len(values),
                "mae": mean_absolute_error(actual, predicted),
                "rmse": mean_squared_error(actual, predicted) ** 0.5,
                "r2": r2_score(actual, predicted),
                "spearman": (
                    spearmanr(actual, predicted).statistic
                    if np.unique(predicted).size > 1
                    else np.nan
                ),
                "top_third_recall": top_third_recall(actual, predicted),
            }
        )
    return pd.DataFrame(rows)


def grouped_importance(d, winner, log_target):
    """Held-region grouped permutation importance, measured as added MAE."""
    X = d[FEATURES]
    y = d[TARGET].to_numpy()
    rows = []
    rng = np.random.default_rng(SEED)
    for repeat, fold, train, test, _ in list(geographic_splits(d))[:N_SPLITS]:
        model = clone(models()[winner])
        if log_target:
            model = TransformedTargetRegressor(
                regressor=model,
                func=np.log1p,
                inverse_func=np.expm1,
                check_inverse=False,
            )
        model.fit(X.iloc[train], y[train])
        baseline = mean_absolute_error(y[test], np.maximum(0, model.predict(X.iloc[test])))
        for group, columns in FEATURE_GROUPS.items():
            for permutation in range(30):
                moved = X.iloc[test].copy()
                order = rng.permutation(len(test))
                moved.loc[:, columns] = moved[columns].to_numpy()[order]
                error = mean_absolute_error(
                    y[test], np.maximum(0, model.predict(moved))
                )
                rows.append(
                    {
                        "fold": fold,
                        "group": group,
                        "permutation": permutation,
                        "added_mae": error - baseline,
                    }
                )
    return pd.DataFrame(rows)


def feature_set_ablation(d):
    """Does the experimental pollution source earn predictive value?"""
    sets = {
        "SVI themes only": FEATURE_GROUPS["SVI themes"],
        "chronic only": FEATURE_GROUPS["chronic conditions"],
        "shade only": FEATURE_GROUPS["modeled shade"],
        "SVI + chronic": [
            *FEATURE_GROUPS["SVI themes"],
            *FEATURE_GROUPS["chronic conditions"],
        ],
        "final-six structural": [
            *FEATURE_GROUPS["SVI themes"],
            *FEATURE_GROUPS["chronic conditions"],
            *FEATURE_GROUPS["modeled shade"],
            *FEATURE_GROUPS["population / urban form"],
        ],
        "expanded + pollution": FEATURES,
    }
    y = d[TARGET].to_numpy()
    rows = []
    for repeat, fold, train, test, _ in geographic_splits(d):
        for label, columns in sets.items():
            base = clone(models()["shallow boosting"])
            model = TransformedTargetRegressor(
                regressor=base,
                func=np.log1p,
                inverse_func=np.expm1,
                check_inverse=False,
            )
            model.fit(d.iloc[train][columns], y[train])
            pred = np.maximum(0, model.predict(d.iloc[test][columns]))
            for index, observed, estimate in zip(test, y[test], pred):
                rows.append(
                    {
                        "repeat": repeat,
                        "fold": fold,
                        "row": index,
                        "feature_set": label,
                        "observed": observed,
                        "predicted": estimate,
                    }
                )
    predictions = pd.DataFrame(rows)
    report = []
    for (repeat, label), values in predictions.groupby(["repeat", "feature_set"]):
        actual = values["observed"].to_numpy()
        predicted = values["predicted"].to_numpy()
        report.append(
            {
                "repeat": repeat,
                "feature_set": label,
                "mae": mean_absolute_error(actual, predicted),
                "r2": r2_score(actual, predicted),
                "spearman": spearmanr(actual, predicted).statistic,
                "top_third_recall": top_third_recall(actual, predicted),
            }
        )
    return pd.DataFrame(report), predictions


def residual_moran(d, predictions, model, target_scale):
    chosen = predictions[
        predictions["split"].eq("spatial")
        & predictions["repeat"].eq(0)
        & predictions["model"].eq(model)
        & predictions["target_scale"].eq(target_scale)
    ].set_index("row")
    frame = d.loc[chosen.index].copy()
    frame["residual"] = (
        chosen.loc[frame.index, "observed"] - chosen.loc[frame.index, "predicted"]
    )
    queen = Queen.from_dataframe(frame, use_index=False, silence_warnings=True)
    mainland = frame.drop(index=queen.islands).reset_index(drop=True)
    w = Queen.from_dataframe(mainland, use_index=False, silence_warnings=True)
    w.transform = "r"
    result = Moran(
        mainland["residual"].to_numpy(),
        w,
        permutations=999,
    )
    return {"morans_I": result.I, "p": result.p_sim, "n": len(mainland)}


def summarize(scores):
    def q25(values):
        return values.quantile(0.25)

    def q75(values):
        return values.quantile(0.75)

    q25.__name__ = "q25"
    q75.__name__ = "q75"
    metrics = ["mae", "rmse", "r2", "spearman", "top_third_recall"]
    return (
        scores.groupby(["split", "target_scale", "model"])[metrics]
        .agg(["median", q25, q75])
        .round(3)
    )


def plot_results(scores, importance):
    spatial = scores[scores["split"].eq("spatial")].copy()
    order = (
        spatial.groupby(["target_scale", "model"])["mae"]
        .median()
        .sort_values()
        .index
    )
    labels = [f"{scale}\n{model}" for scale, model in order]
    values = [
        spatial[
            spatial["target_scale"].eq(scale) & spatial["model"].eq(model)
        ]["mae"]
        for scale, model in order
    ]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.boxplot(values, tick_labels=labels, showfliers=False)
    ax.set_ylabel("held-region mean absolute error")
    ax.set_title("Flexible ML does not automatically generalize across geography")
    ax.tick_params(axis="x", labelrotation=25)
    fig.tight_layout()
    fig.savefig(OUT / "spatial_model_comparison.png", dpi=180)
    plt.close(fig)

    grouped = (
        importance.groupby("group")["added_mae"]
        .agg(["median", lambda x: x.quantile(0.25), lambda x: x.quantile(0.75)])
        .sort_values("median")
    )
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.barh(grouped.index, grouped["median"], color="#4c78a8")
    ax.axvline(0, color="#333333", lw=0.8)
    ax.set_xlabel("increase in held-region MAE after shuffling group")
    ax.set_title("Grouped permutation importance")
    fig.tight_layout()
    fig.savefig(OUT / "grouped_importance.png", dpi=180)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = prepare(load_config())
    print(f"PROTOTYPE: {len(d)} ZCTAs, {len(FEATURES)} predictors, target={TARGET}")
    print("target distribution:")
    print(d[TARGET].describe(percentiles=[0.9, 0.95, 0.99]).round(3).to_string())
    maximum = d.loc[d[TARGET].idxmax(), ["zcta", "place_name", TARGET]]
    print(f"largest outcome: {maximum.to_dict()}")

    all_scores = []
    all_predictions = []
    for scale in (False, True):
        for split, iterator in (
            ("random", random_splits(d)),
            ("spatial", geographic_splits(d)),
        ):
            scores, predictions = evaluate(d, split, iterator, log_target=scale)
            all_scores.append(scores)
            all_predictions.append(predictions)
    scores = pd.concat(all_scores, ignore_index=True)
    predictions = pd.concat(all_predictions, ignore_index=True)
    pooled = pooled_metrics(predictions)

    spatial_medians = (
        pooled[pooled["split"].eq("spatial")]
        .groupby(["target_scale", "model"])["mae"]
        .median()
        .sort_values()
    )
    winning_scale, winner = spatial_medians.index[0]
    print(f"\n=== countywide out-of-fold results across {N_REPEATS} partitions ===")
    print(summarize(pooled).to_string())
    print(f"\nspatial winner: {winner} ({winning_scale} target)")

    importance = grouped_importance(d, winner, winning_scale == "log1p")
    ablation, ablation_predictions = feature_set_ablation(d)
    moran = residual_moran(d, predictions, winner, winning_scale)
    print("\n=== grouped held-region permutation importance ===")
    print(
        importance.groupby("group")["added_mae"]
        .agg(["median", "mean"])
        .sort_values("median", ascending=False)
        .round(3)
        .to_string()
    )
    print(f"\nresidual spatial pattern: {moran}")
    print("\n=== feature-source ablation: log-target shallow boosting ===")
    print(
        ablation.groupby("feature_set")[
            ["mae", "spearman", "top_third_recall", "r2"]
        ]
        .median()
        .sort_values("mae")
        .round(3)
        .to_string()
    )

    # Sensitivity: remove the single extreme outcome and rerun the spatial comparison.
    trimmed = d.drop(index=d[TARGET].idxmax()).reset_index(drop=True)
    trimmed_scores, trimmed_predictions = evaluate(
        trimmed, "spatial_trimmed", geographic_splits(trimmed), log_target=False
    )
    trimmed_pooled = pooled_metrics(trimmed_predictions)
    print("\n=== sensitivity: remove the single largest outcome ===")
    print(
        trimmed_pooled.groupby("model")[["mae", "spearman", "r2"]]
        .median()
        .sort_values("mae")
        .round(3)
        .to_string()
    )

    scores.to_csv(OUT / "fold_scores.csv", index=False)
    pooled.to_csv(OUT / "pooled_repeat_scores.csv", index=False)
    predictions.to_csv(OUT / "out_of_fold_predictions.csv", index=False)
    importance.to_csv(OUT / "grouped_importance.csv", index=False)
    ablation.to_csv(OUT / "feature_ablation_scores.csv", index=False)
    ablation_predictions.to_csv(OUT / "feature_ablation_predictions.csv", index=False)
    trimmed_scores.to_csv(OUT / "trimmed_fold_scores.csv", index=False)
    trimmed_pooled.to_csv(OUT / "trimmed_pooled_repeat_scores.csv", index=False)
    pd.DataFrame([moran]).to_csv(OUT / "residual_moran.csv", index=False)
    plot_results(pooled, importance)
    print(f"\nartifacts -> {OUT}")


if __name__ == "__main__":
    main()
