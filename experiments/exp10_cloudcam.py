"""Experiment 10 -- cloud nowcasting from whole-sky camera images.

Question: can a learned model read the cloud fraction off a whole-sky camera
image accurately enough to serve as the planner's sub-hourly nowcast, and how
much does learning add over the classical colour-ratio rules?

Data: WSISEG database (400 whole-sky images, per-pixel cloud / sky / undefined
labels; Xie et al., 2020). Downloaded by this script into the ignored cache; it
carries no licence file, so it is used for research with citation and is not
redistributed.

Protocol: blocked 5-fold cross-validation over the image sequence (all images
are from one camera, so consecutive frames are near-duplicates and a random
split would leak). Every method sees exactly the same training images in each
fold. Metrics are over valid pixels, plus each image's cloud fraction, which is
what the planner consumes.

Usage:
    python experiments/exp10_cloudcam.py [--epochs 30] [--download]
    python experiments/exp10_cloudcam.py --final-gbm   # only (re)train the deployable GBM
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
from skypass.paths import ML_DATA_DIR  # noqa: E402
from skypass.ml.cloudcam import (WSISEG_DIR, WSISEG_URL, PixelGBM,  # noqa: E402
                                 RatioThreshold, UNet, blocked_folds,
                                 load_wsiseg, segmentation_metrics)

SEED = 20261021
EXAMPLES = (10, 170, 330)          # one test image from folds 1, 3 and 5


def ensure_data(force: bool = False) -> str:
    if os.path.isdir(WSISEG_DIR) and not force:
        return WSISEG_DIR
    base = os.path.dirname(WSISEG_DIR)
    os.makedirs(base, exist_ok=True)
    zpath = os.path.join(base, "wsiseg.zip")
    print(f"  downloading {WSISEG_URL}")
    with urllib.request.urlopen(WSISEG_URL, timeout=600) as r, open(zpath, "wb") as fh:
        fh.write(r.read())
    with zipfile.ZipFile(zpath) as z:
        z.extractall(base)
    return WSISEG_DIR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--final-gbm", action="store_true",
                    help="only train the deployable pixel GBM on all images and "
                         "record it in the existing results file")
    a = ap.parse_args()

    import numpy as np
    import torch
    torch.set_num_threads(max(1, (os.cpu_count() or 2) - 2))

    ensure_data(a.download)
    imgs, labs, names = load_wsiseg()
    if a.final_gbm:
        import json
        from skypass.paths import RESULTS_DIR
        gbm_path = PixelGBM(random_state=SEED).fit(imgs, labs).save()
        print(f"  gbm model -> {gbm_path}")
        rp = os.path.join(RESULTS_DIR, "exp10_cloudcam.json")
        with open(rp, encoding="utf-8") as fh:
            res = json.load(fh)
        res["gbm_model_path"] = os.path.relpath(gbm_path)
        with open(rp, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)
        return
    banner(f"10  Cloud nowcasting from whole-sky images  ({len(imgs)} images, "
           f"{imgs.shape[2]}x{imgs.shape[1]})")

    methods = {
        "ratio_fixed": lambda: RatioThreshold(0.6),
        "ratio_tuned": lambda: RatioThreshold(None),
        "pixel_gbm": lambda: PixelGBM(random_state=SEED),
        "unet": lambda: UNet(epochs=a.epochs, random_state=SEED),
    }
    preds = {k: [None] * len(imgs) for k in methods}
    probs_unet = [None] * len(imgs)
    per_fold = {k: [] for k in methods}
    seconds = {k: 0.0 for k in methods}
    thresholds = []
    for fi, (tr, te) in enumerate(blocked_folds(len(imgs))):
        for k, make in methods.items():
            t0 = time.perf_counter()
            m = make().fit(imgs[tr], labs[tr])
            for j in te:
                if k == "unet":
                    probs_unet[j] = m.predict_proba(imgs[j])
                    preds[k][j] = (probs_unet[j] > 0.5).astype(np.int8)
                else:
                    preds[k][j] = m.predict(imgs[j])
            seconds[k] += time.perf_counter() - t0
            per_fold[k].append(segmentation_metrics([preds[k][j] for j in te], labs[te]))
            if k == "ratio_tuned":
                thresholds.append(m.threshold)
        print(f"  fold {fi + 1}/5: " + "  ".join(
            f"{k} IoU {per_fold[k][-1]['cloud_iou']:.3f}" for k in methods), flush=True)

    pooled = {k: segmentation_metrics(preds[k], labs) for k in methods}
    for k in methods:
        pooled[k]["fold_iou"] = [f["cloud_iou"] for f in per_fold[k]]
        pooled[k]["fold_fraction_mae"] = [f["fraction_mae"] for f in per_fold[k]]
        pooled[k]["seconds"] = seconds[k]
        p = pooled[k]
        print(f"  {k:12} acc {p['pixel_accuracy']:.3f}  IoU {p['cloud_iou']:.3f}  "
              f"F1 {p['cloud_f1']:.3f}  fraction MAE {100 * p['fraction_mae']:.1f} pp  "
              f"r {p['fraction_corr']:.3f}")

    # examples for the figure (kept in the ignored cache: dataset images)
    ex_dir = os.path.join(ML_DATA_DIR, "figures")
    os.makedirs(ex_dir, exist_ok=True)
    np.savez_compressed(os.path.join(ex_dir, "cloudcam_examples.npz"),
                        idx=np.array(EXAMPLES), img=imgs[list(EXAMPLES)],
                        lab=labs[list(EXAMPLES)],
                        ratio=np.stack([preds["ratio_tuned"][j] for j in EXAMPLES]),
                        gbm=np.stack([preds["pixel_gbm"][j] for j in EXAMPLES]),
                        unet=np.stack([probs_unet[j] for j in EXAMPLES]))

    # deployable model: trained on all images
    final = UNet(epochs=a.epochs, random_state=SEED).fit(imgs, labs)
    model_path = final.save()
    print(f"  model -> {model_path}")
    gbm_path = PixelGBM(random_state=SEED).fit(imgs, labs).save()
    print(f"  gbm model -> {gbm_path}")

    save("exp10_cloudcam", {
        "data": {"source": "WSISEG (Xie et al. 2020)", "url": WSISEG_URL,
                 "n_images": int(len(imgs)), "size": [int(imgs.shape[2]), int(imgs.shape[1])],
                 "cameras": 1,
                 "label_share": {"cloud": float(np.mean(labs == 1)),
                                 "sky": float(np.mean(labs == 0)),
                                 "undefined": float(np.mean(labs == -1))}},
        "protocol": {"cv": "blocked 5-fold over the image sequence", "seed": SEED,
                     "unet": {"input": 160, "base_channels": 16, "epochs": a.epochs,
                              "batch": 16, "optimiser": "AdamW, cosine schedule",
                              "augmentation": "90-degree rotations, flips"},
                     "pixel_gbm": {"pixels_per_image": 1500, "features": 15}},
        "pooled": pooled, "tuned_thresholds": thresholds,
        "unet_final_loss": final.history[-1], "model_path": os.path.relpath(model_path),
        "gbm_model_path": os.path.relpath(gbm_path),
    })


if __name__ == "__main__":
    main()
