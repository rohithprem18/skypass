"""Experiment 11 -- learned satellite brightness.

Question: can a model trained on measured magnitudes predict how bright a
satellite will look during a pass better than the diffuse-sphere photometry the
planner uses, and does that change the visibility decision at the naked-eye
limit?

Data: IAU CPS SCORE (free and open; acknowledgement in the paper). Every row
carries the measured magnitude and the SatChecker geometry at observation time.

Protocol, chosen so no result leaks:
  * 5-fold GroupKFold by NORAD identifier: every prediction is for a satellite
    absent from training, the realistic case for a planner (most objects it
    schedules have never been measured).
  * a temporal check: train on observations before the split date, test after.
  * three predictors with identical inputs: SkyPass's sphere, the sphere with
    per-family standard magnitudes fitted on the training fold, and
    gradient-boosted trees.
  * metrics pooled over observations and averaged per satellite (a few objects
    have hundreds of rows), plus the visible / not-visible decision at m = 6.

The final model, trained on all clean rows, is saved to cache/ml/models for the
planner's optional learned photometry.

Usage:
    python experiments/exp11_brightness.py [--download]
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import banner, save  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from skypass.ml.brightness import (SCORE_CSV, SCORE_URL, BrightnessModel,  # noqa: E402
                                   SphereBaseline, load_score,
                                   regression_metrics)

SPLIT_DATE = "2025-07-01"
SEED = 20261021


def ensure_data(force: bool = False) -> str:
    if os.path.exists(SCORE_CSV) and not force:
        return SCORE_CSV
    os.makedirs(os.path.dirname(SCORE_CSV), exist_ok=True)
    zpath = os.path.join(os.path.dirname(SCORE_CSV), "score_all.zip")
    print(f"  downloading {SCORE_URL}")
    req = urllib.request.Request(SCORE_URL, headers={"User-Agent": "skypass-exp11"})
    with urllib.request.urlopen(req, timeout=300) as r, open(zpath, "wb") as fh:
        fh.write(r.read())
    with zipfile.ZipFile(zpath) as z:
        z.extractall(os.path.dirname(SCORE_CSV))
    return SCORE_CSV


def per_satellite_mae(df, pred):
    import numpy as np
    err = np.abs(np.asarray(pred) - df["mag"].to_numpy())
    per = df.assign(err=err).groupby("norad")["err"].mean()
    return float(per.mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true", help="re-download SCORE")
    a = ap.parse_args()

    import numpy as np
    from sklearn.inspection import permutation_importance
    from sklearn.model_selection import GroupKFold

    ensure_data(a.download)
    df = load_score()
    banner(f"11  Learned satellite brightness  ({len(df)} observations, "
           f"{df.norad.nunique()} satellites)")

    predictors = {
        "sphere_skypass": lambda: SphereBaseline(fitted=False),
        "sphere_fitted": lambda: SphereBaseline(fitted=True),
        "learned_hgb": lambda: BrightnessModel(random_state=SEED),
    }

    # ---- grouped cross-validation (unseen satellites) ---------------------
    folds = GroupKFold(n_splits=5)
    oof = {k: np.zeros(len(df)) for k in predictors}
    importance = None
    t0 = time.perf_counter()
    for fi, (tr, te) in enumerate(folds.split(df, groups=df["norad"])):
        for k, make in predictors.items():
            m = make().fit(df.iloc[tr])
            oof[k][te] = m.predict(df.iloc[te])
            if k == "learned_hgb" and fi == 0:
                r = permutation_importance(m.model, m.features(df.iloc[te]),
                                           df["mag"].to_numpy()[te], n_repeats=5,
                                           random_state=SEED, scoring="neg_mean_absolute_error")
                importance = {n: float(v) for n, v in
                              zip(BrightnessModel.FEATURE_NAMES, r.importances_mean)}
        print(f"  fold {fi + 1}/5 done")
    cv_seconds = time.perf_counter() - t0

    grouped = {}
    for k in predictors:
        met = regression_metrics(df["mag"], oof[k])
        met["per_satellite_mae"] = per_satellite_mae(df, oof[k])
        grouped[k] = met
    by_family = {}
    for fam, idx in df.groupby("family").indices.items():
        by_family[fam] = {"n": int(len(idx)), "satellites": int(df.iloc[idx].norad.nunique()),
                          **{k: float(np.mean(np.abs(oof[k][idx] - df["mag"].to_numpy()[idx])))
                             for k in predictors}}

    # ---- temporal check ---------------------------------------------------
    split = np.datetime64(SPLIT_DATE)
    tmask = df["time"].dt.tz_convert(None).to_numpy() < split
    tr, te = np.where(tmask)[0], np.where(~tmask)[0]
    temporal = {"split_date": SPLIT_DATE, "n_train": int(len(tr)), "n_test": int(len(te))}
    test_df = df.iloc[te]
    train_counts = df.iloc[tr]["family"].value_counts()
    # families with at least 50 training rows count as "established"
    est = test_df["family"].map(lambda f: train_counts.get(f, 0) >= 50).to_numpy()
    temporal["n_test_established"] = int(est.sum())
    temporal["n_test_new_or_rare"] = int((~est).sum())
    temporal["train_families"] = sorted(train_counts.index.tolist())
    temporal["test_only_families"] = sorted(set(test_df["family"]) - set(train_counts.index))
    t_err = {}
    for k, make in predictors.items():
        m = make().fit(df.iloc[tr])
        p = m.predict(test_df)
        temporal[k] = regression_metrics(test_df["mag"].to_numpy(), p)
        e = np.abs(p - test_df["mag"].to_numpy())
        t_err[k] = e
        temporal[k]["mae_established"] = float(e[est].mean())
        temporal[k]["mae_new_or_rare"] = float(e[~est].mean())
    temporal["by_family_mae"] = {
        fam: {"n": int(len(idx)), **{k: float(t_err[k][idx].mean()) for k in predictors}}
        for fam, idx in test_df.reset_index(drop=True).groupby("family").indices.items()}

    # ---- final model for the planner ---------------------------------------
    final = BrightnessModel(random_state=SEED).fit(df)
    model_path = final.save()

    for k in predictors:
        g = grouped[k]
        print(f"  {k:15} MAE {g['mae']:.3f}  RMSE {g['rmse']:.3f}  per-sat MAE "
              f"{g['per_satellite_mae']:.3f}  |err|<=0.5 {g['within_0p5']:.1%}  "
              f"vis bal.acc {g['visibility_balanced_accuracy']:.3f}")
    print(f"  temporal ({SPLIT_DATE}):", {k: round(temporal[k]['mae'], 3) for k in predictors})
    print(f"  importance (MAE increase):", {k: round(v, 3) for k, v in importance.items()})
    print(f"  model -> {model_path}")

    save("exp11_brightness", {
        "data": {"source": "IAU CPS SCORE", "url": SCORE_URL,
                 "n_observations": int(len(df)), "n_satellites": int(df.norad.nunique()),
                 "excluded": ["ACS 3", "potentially_discrepant", "not illuminated",
                              "below horizon"],
                 "time_range": [str(df.time.min()), str(df.time.max())],
                 "families": df.family.value_counts().to_dict()},
        "protocol": {"cv": "GroupKFold(5) by NORAD id", "seed": SEED,
                     "visibility_limit_mag": 6.0},
        "grouped_cv": grouped, "by_family": by_family, "temporal": temporal,
        "permutation_importance_mae": importance, "cv_seconds": cv_seconds,
        "model_path": os.path.relpath(model_path),
    })


if __name__ == "__main__":
    main()
