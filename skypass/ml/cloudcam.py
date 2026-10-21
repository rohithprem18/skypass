"""Cloud nowcasting from whole-sky camera images.

The forecast experiments show a cloud forecast cannot help a station that must
observe every night: cloud persists through a night, so reordering passes inside
it gains nothing, and only sub-hourly information could. A whole-sky camera is
that information. This module segments cloud in a camera image and reports the
sky's cloud fraction, which :func:`skypass.pipeline.plan` accepts as a nowcast
for the next hour (``nowcast=``; CLI ``plan --sky-image``).

Methods, all evaluated on the WSISEG database (400 whole-sky images with
per-pixel cloud / sky / undefined labels):

* ``RatioThreshold``: the classical red/blue ratio rule (cloud if R/B > t), with
  the long-standing fixed t = 0.6 or t tuned on the training images.
* ``PixelGBM``: gradient-boosted trees on per-pixel colour and local texture.
* ``UNet``: a small convolutional encoder-decoder trained end to end.

Requires numpy and Pillow; scikit-learn for ``PixelGBM``; PyTorch for ``UNet``.
"""
from __future__ import annotations

import glob
import os
from typing import Dict, Iterable, List, Optional, Tuple

from ..paths import ML_DATA_DIR, MODEL_DIR

WSISEG_URL = "https://codeload.github.com/CV-Application/WSISEG-Database/zip/refs/heads/master"
WSISEG_DIR = os.path.join(ML_DATA_DIR, "wsiseg", "WSISEG-Database-master")
DEFAULT_UNET_PATH = os.path.join(MODEL_DIR, "cloudcam_unet.pt")
DEFAULT_GBM_PATH = os.path.join(MODEL_DIR, "cloudcam_gbm.pkl")

IGNORE = -1        # undefined pixels (outside the fisheye, obstructions)


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
def load_wsiseg(root: str = WSISEG_DIR):
    """Images (N, H, W, 3) uint8 and labels (N, H, W) int8: 1 cloud, 0 sky, -1 ignore.

    WSISEG annotations mark cloud 255, clear sky 100, undefined 0.
    """
    import numpy as np
    from PIL import Image

    names = sorted(os.path.basename(p) for p in glob.glob(os.path.join(root, "whole sky images", "*")))
    imgs, labs = [], []
    for n in names:
        imgs.append(np.asarray(Image.open(os.path.join(root, "whole sky images", n)).convert("RGB")))
        a = np.asarray(Image.open(os.path.join(root, "annotation", n)))
        lab = np.full(a.shape, IGNORE, dtype=np.int8)
        lab[a == 255] = 1
        lab[a == 100] = 0
        labs.append(lab)
    return np.stack(imgs), np.stack(labs), names


def blocked_folds(n: int, k: int = 5) -> List[Tuple[List[int], List[int]]]:
    """Contiguous blocks: consecutive frames of one camera are near-duplicates,
    so a random split would leak; each test fold is one contiguous run."""
    edges = [round(i * n / k) for i in range(k + 1)]
    out = []
    for i in range(k):
        te = list(range(edges[i], edges[i + 1]))
        tr = [j for j in range(n) if j < edges[i] or j >= edges[i + 1]]
        out.append((tr, te))
    return out


# ----------------------------------------------------------------------------
# Features and classical rules
# ----------------------------------------------------------------------------
def _box(a, r: int):
    """Mean over a (2r+1)^2 window via an integral image (no SciPy needed)."""
    import numpy as np
    p = np.pad(a, r, mode="edge").astype(np.float64)
    c = p.cumsum(0).cumsum(1)
    c = np.pad(c, ((1, 0), (1, 0)))
    k = 2 * r + 1
    s = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return (s / (k * k)).astype(np.float32)


def pixel_features(img) -> "object":
    """Per-pixel features (H*W, F): colour ratios, saturation, brightness and
    their local means and spread at two scales."""
    import numpy as np
    x = img.astype(np.float32) / 255.0
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    eps = 1e-3
    rb = r / (b + eps)
    nbr = (b - r) / (b + r + eps)
    mx, mn = x.max(-1), x.min(-1)
    sat = (mx - mn) / (mx + eps)
    val = mx
    feats = [r, g, b, rb, nbr, sat, val]
    for f in (nbr, val):
        for rad in (2, 7):
            m = _box(f, rad)
            feats.append(m)
            feats.append(np.sqrt(np.maximum(_box(f * f, rad) - m * m, 0)))
    return np.stack(feats, -1).reshape(-1, len(feats))


class RatioThreshold:
    """Cloud where R/B exceeds a threshold (0.6 is the classical choice)."""

    def __init__(self, threshold: Optional[float] = 0.6):
        self.threshold = threshold

    def fit(self, imgs, labs) -> "RatioThreshold":
        """Tune the threshold on training pixels when constructed with None."""
        import numpy as np
        if self.threshold is None:
            rb, y = self._ratio_and_labels(imgs, labs)
            grid = np.linspace(0.3, 1.2, 181)
            acc = [np.mean((rb > t) == y) for t in grid]
            self.threshold = float(grid[int(np.argmax(acc))])
        return self

    @staticmethod
    def _ratio_and_labels(imgs, labs, max_pixels: int = 2_000_000):
        import numpy as np
        x = imgs.astype(np.float32)
        rb = (x[..., 0] / (x[..., 2] + 1.0)).ravel()
        y = labs.ravel()
        keep = y != IGNORE
        rb, y = rb[keep], y[keep] == 1
        if len(y) > max_pixels:
            idx = np.random.default_rng(0).choice(len(y), max_pixels, replace=False)
            rb, y = rb[idx], y[idx]
        return rb, y

    def predict(self, img):
        import numpy as np
        x = img.astype(np.float32)
        return (x[..., 0] / (x[..., 2] + 1.0) > self.threshold).astype(np.int8)


class PixelGBM:
    """Gradient-boosted trees on :func:`pixel_features`."""

    def __init__(self, pixels_per_image: int = 1500, random_state: int = 0):
        self.ppi = pixels_per_image
        self.random_state = random_state
        self.model = None

    def fit(self, imgs, labs) -> "PixelGBM":
        import numpy as np
        from sklearn.ensemble import HistGradientBoostingClassifier
        rng = np.random.default_rng(self.random_state)
        X, y = [], []
        for img, lab in zip(imgs, labs):
            f = pixel_features(img)
            l = lab.ravel()
            valid = np.flatnonzero(l != IGNORE)
            pick = rng.choice(valid, min(self.ppi, len(valid)), replace=False)
            X.append(f[pick]); y.append(l[pick])
        self.model = HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.08, max_leaf_nodes=63,
            l2_regularization=1.0, random_state=self.random_state)
        self.model.fit(np.concatenate(X), np.concatenate(y))
        return self

    def predict(self, img):
        import numpy as np
        p = self.model.predict(pixel_features(img))
        return p.reshape(img.shape[:2]).astype(np.int8)

    def save(self, path: str = DEFAULT_GBM_PATH) -> str:
        import pickle
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            pickle.dump({"model": self.model, "ppi": self.ppi,
                         "random_state": self.random_state}, fh)
        return path

    @classmethod
    def load(cls, path: str = DEFAULT_GBM_PATH) -> "PixelGBM":
        import pickle
        with open(path, "rb") as fh:
            d = pickle.load(fh)
        m = cls(d["ppi"], d["random_state"])
        m.model = d["model"]
        return m


# ----------------------------------------------------------------------------
# U-Net
# ----------------------------------------------------------------------------
def _unet(base: int = 16):
    import torch
    from torch import nn

    def block(i, o):
        return nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
                             nn.Conv2d(o, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True))

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.e1, self.e2, self.e3 = block(3, base), block(base, 2 * base), block(2 * base, 4 * base)
            self.mid = block(4 * base, 8 * base)
            self.u3, self.d3 = nn.ConvTranspose2d(8 * base, 4 * base, 2, 2), block(8 * base, 4 * base)
            self.u2, self.d2 = nn.ConvTranspose2d(4 * base, 2 * base, 2, 2), block(4 * base, 2 * base)
            self.u1, self.d1 = nn.ConvTranspose2d(2 * base, base, 2, 2), block(2 * base, base)
            self.out = nn.Conv2d(base, 1, 1)
            self.pool = nn.MaxPool2d(2)

        def forward(self, x):
            e1 = self.e1(x)
            e2 = self.e2(self.pool(e1))
            e3 = self.e3(self.pool(e2))
            m = self.mid(self.pool(e3))
            d3 = self.d3(torch.cat([self.u3(m), e3], 1))
            d2 = self.d2(torch.cat([self.u2(d3), e2], 1))
            d1 = self.d1(torch.cat([self.u1(d2), e1], 1))
            return self.out(d1)

    return Net()


class UNet:
    """Small U-Net trained with a masked binary cross-entropy (undefined pixels
    contribute nothing). Images are resized to ``size`` for training and the
    logits upsampled back, so evaluation is at the label resolution."""

    def __init__(self, size: int = 160, base: int = 16, epochs: int = 40,
                 batch: int = 16, lr: float = 2e-3, random_state: int = 0):
        self.size, self.base, self.epochs = size, base, epochs
        self.batch, self.lr, self.random_state = batch, lr, random_state
        self.net = None
        self.history: List[float] = []

    def _tensor(self, imgs, labs=None):
        import numpy as np
        import torch
        import torch.nn.functional as F
        x = torch.from_numpy(imgs.astype(np.float32) / 255.0).permute(0, 3, 1, 2)
        x = F.interpolate(x, size=(self.size, self.size), mode="bilinear", align_corners=False)
        if labs is None:
            return x
        y = torch.from_numpy(labs.astype(np.float32)).unsqueeze(1)
        y = F.interpolate(y, size=(self.size, self.size), mode="nearest")
        return x, y

    def fit(self, imgs, labs) -> "UNet":
        import torch
        torch.manual_seed(self.random_state)
        x, y = self._tensor(imgs, labs)
        self.net = _unet(self.base)
        opt = torch.optim.AdamW(self.net.parameters(), lr=self.lr, weight_decay=1e-4)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, self.epochs)
        bce = torch.nn.BCEWithLogitsLoss(reduction="none")
        g = torch.Generator().manual_seed(self.random_state)
        self.net.train()
        for _ in range(self.epochs):
            perm = torch.randperm(len(x), generator=g)
            total = 0.0
            for i in range(0, len(x), self.batch):
                idx = perm[i:i + self.batch]
                xb, yb = x[idx], y[idx]
                # rotations and flips: the fisheye sky has no preferred azimuth
                k = int(torch.randint(0, 4, (1,), generator=g))
                xb, yb = torch.rot90(xb, k, (2, 3)), torch.rot90(yb, k, (2, 3))
                if torch.rand(1, generator=g) < 0.5:
                    xb, yb = xb.flip(3), yb.flip(3)
                valid = (yb >= 0).float()
                loss = (bce(self.net(xb), yb.clamp(min=0)) * valid).sum() / valid.sum().clamp(min=1)
                opt.zero_grad()
                loss.backward()
                opt.step()
                total += float(loss.detach()) * len(idx)
            sched.step()
            self.history.append(total / len(x))
        return self

    def predict_proba(self, img):
        import numpy as np
        import torch
        import torch.nn.functional as F
        self.net.eval()
        with torch.no_grad():
            logit = self.net(self._tensor(img[None]))
            logit = F.interpolate(logit, size=img.shape[:2], mode="bilinear", align_corners=False)
        return torch.sigmoid(logit)[0, 0].numpy().astype(np.float32)

    def predict(self, img):
        import numpy as np
        return (self.predict_proba(img) > 0.5).astype(np.int8)

    def save(self, path: str = DEFAULT_UNET_PATH) -> str:
        import torch
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save({"state": self.net.state_dict(), "size": self.size, "base": self.base}, path)
        return path

    @classmethod
    def load(cls, path: str = DEFAULT_UNET_PATH) -> "UNet":
        import torch
        ck = torch.load(path, map_location="cpu", weights_only=True)
        m = cls(size=ck["size"], base=ck["base"])
        m.net = _unet(m.base)
        m.net.load_state_dict(ck["state"])
        return m


# ----------------------------------------------------------------------------
# Metrics and the nowcast
# ----------------------------------------------------------------------------
def segmentation_metrics(preds: Iterable, labs: Iterable) -> Dict[str, float]:
    """Pixel accuracy, cloud precision / recall / F1 / IoU over valid pixels,
    and the error in each image's cloud fraction (the quantity the planner uses)."""
    import numpy as np
    tp = fp = fn = tn = 0
    frac_err, frac_true, frac_pred = [], [], []
    for p, l in zip(preds, labs):
        v = l != IGNORE
        pv, lv = p[v] == 1, l[v] == 1
        tp += int(np.sum(pv & lv)); fp += int(np.sum(pv & ~lv))
        fn += int(np.sum(~pv & lv)); tn += int(np.sum(~pv & ~lv))
        frac_true.append(lv.mean()); frac_pred.append(pv.mean())
        frac_err.append(abs(pv.mean() - lv.mean()))
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    return {"pixel_accuracy": (tp + tn) / max(tp + tn + fp + fn, 1),
            "cloud_precision": prec, "cloud_recall": rec,
            "cloud_f1": 2 * prec * rec / max(prec + rec, 1e-12),
            "cloud_iou": tp / max(tp + fp + fn, 1),
            "fraction_mae": float(np.mean(frac_err)),
            "fraction_corr": float(np.corrcoef(frac_true, frac_pred)[0, 1])
            if len(frac_true) > 2 else float("nan"),
            "n_images": len(frac_err)}


def default_segmenter():
    """The deployable segmenter: the pixel GBM if trained (the most accurate in
    experiment 10), otherwise the U-Net."""
    if os.path.exists(DEFAULT_GBM_PATH):
        return PixelGBM.load()
    return UNet.load()


def cloud_fraction(image, model=None, mask=None) -> float:
    """Cloud fraction of a whole-sky image with a trained segmenter
    (:func:`default_segmenter` unless ``model`` is given).

    ``image`` is a path or an (H, W, 3) array. ``mask`` (H, W, bool) marks the
    sky region; by default the brightest-disc heuristic below is used, which
    excludes the black surround of a fisheye frame.
    """
    import numpy as np
    from PIL import Image
    if isinstance(image, str):
        image = np.asarray(Image.open(image).convert("RGB"))
    model = model or default_segmenter()
    pred = model.predict(image)
    if mask is None:
        mask = image.max(-1) > 20
    return float(pred[mask].mean()) if mask.any() else 0.0
