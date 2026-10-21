"""Learned apparent-magnitude model for satellite passes.

SkyPass's photometric gate uses the diffuse-sphere relation

    m = m_std + 5 log10(d / 1000 km) - 2.5 log10 F(psi)

with a standard magnitude ``m_std`` taken from a small table (5.0 for anything
not in it). Real satellites are flat panels, antennas and solar arrays, so the
sphere only orders passes by brightness; it does not predict it. This module
learns the mapping from pass geometry to measured magnitude from the IAU CPS
Satellite Constellation Observation Repository (SCORE), whose rows carry the
observed magnitude together with the SatChecker geometry at the observation
time (phase angle, range, elevation, solar elevation, orbital altitude).

Three predictors share one interface so they can be compared fairly:

* ``SphereBaseline(fitted=False)``: the current SkyPass model.
* ``SphereBaseline(fitted=True)``: the same physics with one standard magnitude
  per satellite family, fitted on the training data (the strongest baseline
  that uses the same information as the learned model).
* ``BrightnessModel``: gradient-boosted trees on the geometry, the sphere
  prediction, the satellite family and the observing band.

Nothing here is imported by the core planner. Requires numpy, pandas and
scikit-learn (``pip install skypass[ml]``).
"""
from __future__ import annotations

import math
import os
import pickle
from typing import Dict, Optional, Sequence

from ..config import DEFAULT_STANDARD_MAGNITUDE
from ..geometry import apparent_magnitude
from ..paths import ML_DATA_DIR, MODEL_DIR
from ..scoring import standard_magnitude

SCORE_URL = "https://score.cps.iau.org/download-all"
SCORE_CSV = os.path.join(ML_DATA_DIR, "score", "satellite_observations_all.csv")
DEFAULT_MODEL_PATH = os.path.join(MODEL_DIR, "brightness_hgb.pkl")

#: Satellite families recognised from the catalogue name. A family is known at
#: planning time for any object, observed before or not, which is why it is a
#: legitimate feature for satellites the model has never seen.
FAMILIES = ("STARLINK", "ONEWEB", "KUIPER", "SPACEMOBILE", "BLUEWALKER",
            "QIANFAN", "HULIANWANG", "GUOWANG", "PELICAN", "TIANQI")

#: Observing bands grouped coarsely. Visual and unfiltered CMOS/CCD estimates
#: approximate V; planning predictions are made for ``VISUAL``.
BANDS = ("VISUAL", "CLEAR", "V", "g", "r", "i", "G", "OTHER")

GEOMETRY = ("phase_deg", "range_km", "elev_deg", "sun_elev_deg", "sat_alt_km")

#: Objects excluded from training and evaluation. ACS 3 is NASA's solar-sail
#: demonstrator: an atypical reflector that alone supplies 58 % of SCORE rows
#: and would otherwise dominate both the fit and the error statistics.
EXCLUDED_NAMES = ("ACS 3",)


def satellite_family(name: str) -> str:
    """Coarse object class from the catalogue name."""
    n = str(name).upper()
    for fam in FAMILIES:
        if fam in n:
            return fam
    if "G60" in n:                     # Qianfan / Spacesail designation
        return "QIANFAN"
    if "R/B" in n:
        return "ROCKET BODY"
    if "DEB" in n:
        return "DEBRIS"
    return "OTHER"


def observing_band(mode: str, filt: str) -> str:
    """Map SCORE's observing mode and filter onto :data:`BANDS`."""
    mode = str(mode).upper()
    if mode == "VISUAL":
        return "VISUAL"
    f = str(filt).strip()
    if f.upper() in ("CLEAR", "LUM", "NONE", "NAN", ""):
        return "CLEAR"
    if f in ("V", "g", "r", "i"):
        return f
    if f.upper().startswith("GAIA"):
        return "G"
    return "OTHER"


def sphere_magnitude(std_mag: float, range_km: float, phase_deg: float) -> float:
    """Diffuse-sphere magnitude, exactly as SkyPass's scoring computes it."""
    return apparent_magnitude(std_mag, range_km, math.radians(phase_deg))


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
def load_score(path: str = SCORE_CSV, exclude: Sequence[str] = EXCLUDED_NAMES):
    """Load SCORE observations and keep the rows a planner can learn from.

    Kept: a measured magnitude, complete SatChecker geometry, flagged as
    illuminated, not flagged as potentially discrepant, satellite above the
    horizon, and not one of ``exclude``. Returns a pandas DataFrame with the
    columns the models use.
    """
    import pandas as pd

    raw = pd.read_csv(path, low_memory=False)
    geom = {"phase_angle_deg_satchecker": "phase_deg",
            "range_to_sat_km_satchecker": "range_km",
            "alt_deg_satchecker": "elev_deg",
            "solar_elevation_deg_satchecker": "sun_elev_deg",
            "sat_altitude_km_satchecker": "sat_alt_km"}
    keep = (raw["apparent_magnitude"].notna()
            & raw[list(geom)].notna().all(axis=1)
            & (raw["illuminated"] == True)            # noqa: E712 (pandas mask)
            & (raw["potentially_discrepant"] != True)  # noqa: E712
            & (raw["alt_deg_satchecker"] > 0)
            & ~raw["satellite_name"].isin(list(exclude)))
    df = raw.loc[keep].rename(columns=geom)
    out = pd.DataFrame({
        "norad": df["norad_cat_id"].astype(int),
        "name": df["satellite_name"].astype(str),
        "time": pd.to_datetime(df["observation_time_utc"], utc=True, errors="coerce"),
        "mag": df["apparent_magnitude"].astype(float),
        "mag_err": df["apparent_magnitude_uncertainty"].astype(float),
        **{c: df[c].astype(float) for c in GEOMETRY},
    })
    out["family"] = out["name"].map(satellite_family)
    out["band"] = [observing_band(m, f) for m, f in
                   zip(df["observing_mode"], df["observing_filter"])]
    return out.reset_index(drop=True)


def _sphere_column(df, std_mags) -> "object":
    import numpy as np
    return np.array([sphere_magnitude(s, r, p) for s, r, p in
                     zip(std_mags, df["range_km"], df["phase_deg"])])


# ----------------------------------------------------------------------------
# Predictors
# ----------------------------------------------------------------------------
class SphereBaseline:
    """Diffuse-sphere photometry.

    ``fitted=False`` reproduces SkyPass: standard magnitudes from the catalogue
    table, 5.0 otherwise. ``fitted=True`` replaces them with one standard
    magnitude per family, the median that makes the sphere match the training
    data, falling back to the global median for an unseen family.
    """

    def __init__(self, fitted: bool = False):
        self.fitted = fitted
        self.family_std: Dict[str, float] = {}
        self.global_std = DEFAULT_STANDARD_MAGNITUDE

    def fit(self, df) -> "SphereBaseline":
        if self.fitted:
            import numpy as np
            # sphere magnitude with m_std = 0 is the pure geometry term; the
            # offset to the observation is the standard magnitude.
            geo = _sphere_column(df, [0.0] * len(df))
            offset = df["mag"].to_numpy() - geo
            self.global_std = float(np.median(offset))
            for fam, idx in df.groupby("family").indices.items():
                self.family_std[fam] = float(np.median(offset[idx]))
        return self

    def predict(self, df):
        if self.fitted:
            stds = [self.family_std.get(f, self.global_std) for f in df["family"]]
        else:
            stds = [standard_magnitude(n) for n in df["name"]]
        return _sphere_column(df, stds)


class BrightnessModel:
    """Gradient-boosted trees on geometry, sphere prediction, family and band."""

    def __init__(self, random_state: int = 0, **hgb_params):
        self.random_state = random_state
        self.hgb_params = {"max_iter": 400, "learning_rate": 0.05,
                           "max_leaf_nodes": 31, "min_samples_leaf": 40,
                           "l2_regularization": 1.0, **hgb_params}
        self.model = None
        self.families = list(FAMILIES) + ["ROCKET BODY", "DEBRIS", "OTHER"]
        self.bands = list(BANDS)

    # -- features -------------------------------------------------------------
    def features(self, df):
        import numpy as np
        sphere = SphereBaseline(fitted=False).predict(df)
        fam = np.array([self.families.index(f) if f in self.families
                        else self.families.index("OTHER") for f in df["family"]])
        band = np.array([self.bands.index(b) if b in self.bands
                         else self.bands.index("OTHER") for b in df["band"]])
        X = np.column_stack([
            df["phase_deg"].to_numpy(),
            np.log10(df["range_km"].to_numpy()),
            df["elev_deg"].to_numpy(),
            df["sun_elev_deg"].to_numpy(),
            np.log10(df["sat_alt_km"].to_numpy()),
            sphere,
            fam, band,
        ])
        return X

    FEATURE_NAMES = ("phase angle", "log range", "elevation", "solar elevation",
                     "log orbital altitude", "sphere prediction", "family", "band")

    def fit(self, df) -> "BrightnessModel":
        from sklearn.ensemble import HistGradientBoostingRegressor
        self.model = HistGradientBoostingRegressor(
            categorical_features=[6, 7], random_state=self.random_state,
            **self.hgb_params)
        self.model.fit(self.features(df), df["mag"].to_numpy())
        return self

    def predict(self, df):
        if self.model is None:
            raise RuntimeError("BrightnessModel is not fitted")
        return self.model.predict(self.features(df))

    def predict_pass(self, name: str, range_km: float, phase_deg: float,
                     elev_deg: float, sun_elev_deg: float, sat_alt_km: float,
                     band: str = "VISUAL") -> float:
        """Apparent magnitude of one object at one instant of a pass."""
        import pandas as pd
        row = pd.DataFrame([{"name": name, "family": satellite_family(name),
                             "band": band, "range_km": range_km,
                             "phase_deg": phase_deg, "elev_deg": elev_deg,
                             "sun_elev_deg": sun_elev_deg,
                             "sat_alt_km": sat_alt_km}])
        return float(self.predict(row)[0])

    # -- persistence ----------------------------------------------------------
    def save(self, path: str = DEFAULT_MODEL_PATH) -> str:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            pickle.dump(self, fh)
        return path

    @staticmethod
    def load(path: str = DEFAULT_MODEL_PATH) -> "BrightnessModel":
        with open(path, "rb") as fh:
            return pickle.load(fh)


_CACHED: Optional[BrightnessModel] = None


def default_model() -> Optional[BrightnessModel]:
    """The trained model from :data:`DEFAULT_MODEL_PATH`, or None if absent."""
    global _CACHED
    if _CACHED is None and os.path.exists(DEFAULT_MODEL_PATH):
        _CACHED = BrightnessModel.load(DEFAULT_MODEL_PATH)
    return _CACHED


# ----------------------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------------------
def regression_metrics(y, yhat, limit: float = 6.0) -> Dict[str, float]:
    """Errors in magnitudes, and the visibility decision at ``limit``.

    The decision metrics matter for SkyPass because the planner gates passes
    at the naked-eye limit: a model is useful if it says "visible" when the
    object really was brighter than ``limit``.
    """
    import numpy as np
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    err = yhat - y
    vis, pvis = y <= limit, yhat <= limit
    tpr = (pvis & vis).sum() / max(vis.sum(), 1)
    tnr = (~pvis & ~vis).sum() / max((~vis).sum(), 1)
    return {"n": int(len(y)),
            "mae": float(np.mean(np.abs(err))),
            "rmse": float(np.sqrt(np.mean(err ** 2))),
            "median_ae": float(np.median(np.abs(err))),
            "bias": float(np.mean(err)),
            "within_0p5": float(np.mean(np.abs(err) <= 0.5)),
            "within_1p0": float(np.mean(np.abs(err) <= 1.0)),
            "visibility_accuracy": float(np.mean(pvis == vis)),
            "visibility_balanced_accuracy": float((tpr + tnr) / 2)}
