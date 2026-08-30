"""Cloud-cover forecasts and verification data (Open-Meteo).

Three distinct products are needed, and keeping them straight is what makes the
evaluation honest:

``forecast``
    What a planner can know *now* about the next 16 days. This is what SkyPass
    uses operationally.
``reanalysis``
    ERA5 hourly total cloud cover for a past interval. This is the verification
    truth: what the sky actually did.
``previous_runs``
    The forecast that *was issued* 1-7 days ahead of a past timestamp. This lets
    us score forecast skill against lead time without waiting a week.

All three are free and keyless. Responses are cached on disk, so an experiment
re-run is deterministic and does not hammer the service.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .config import Site
from .paths import CACHE_DIR
from .timeutil import as_naive_utc, hour_key

FORECAST_API = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_API = "https://archive-api.open-meteo.com/v1/archive"
HISTORICAL_FORECAST_API = "https://historical-forecast-api.open-meteo.com/v1/forecast"
PREVIOUS_RUNS_API = "https://previous-runs-api.open-meteo.com/v1/forecast"

DEFAULT_CACHE_DIR = CACHE_DIR


class WeatherUnavailable(RuntimeError):
    """Raised when the service cannot be reached after retries."""


# ---------------------------------------------------------------------------
# HTTP with cache + retry
# ---------------------------------------------------------------------------
def _cache_file(cache_dir: str, url: str) -> str:
    h = hashlib.sha256(url.encode()).hexdigest()[:24]
    return os.path.join(cache_dir, f"om-{h}.json")


def _fetch_json(url: str, cache_dir: Optional[str] = DEFAULT_CACHE_DIR,
                retries: int = 4, timeout: float = 60.0,
                use_cache: bool = True) -> dict:
    """GET a JSON document, with on-disk caching and exponential backoff.

    Open-Meteo intermittently answers 502 under load; a bare request is not
    reliable enough to build an experiment on.
    """
    path = None
    if cache_dir and use_cache:
        os.makedirs(cache_dir, exist_ok=True)
        path = _cache_file(cache_dir, url)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:
                pass                     # corrupt cache entry -> refetch

    last: Optional[Exception] = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "SkyPass/1.0 (research)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode())
            if path:
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(data, fh)
            return data
        except Exception as exc:                       # noqa: BLE001
            last = exc
            time.sleep(1.5 * (2 ** attempt))
    raise WeatherUnavailable(f"{url}\n  last error: {last}")


# ---------------------------------------------------------------------------
# Cloud series
# ---------------------------------------------------------------------------
@dataclass
class CloudSeries:
    """Hourly cloud fraction in [0, 1], keyed by ``YYYY-MM-DDTHH:00``."""

    values: Dict[str, float]
    label: str = ""

    def __len__(self) -> int:
        return len(self.values)

    def at(self, t: dt.datetime) -> Optional[float]:
        """Cloud fraction at an arbitrary instant, linear between hour marks.

        Cloud cover is a continuous field sampled hourly; snapping to the
        containing hour introduces a bias of up to 30 min against pass times,
        which for a 6-minute pass is the difference between clear and overcast.
        """
        t = as_naive_utc(t)
        h0 = t.replace(minute=0, second=0, microsecond=0)
        v0 = self.values.get(hour_key(h0))
        if v0 is None:
            return None
        v1 = self.values.get(hour_key(h0 + dt.timedelta(hours=1)))
        if v1 is None:
            return v0
        frac = (t - h0).total_seconds() / 3600.0
        return v0 + (v1 - v0) * frac

    def clear_fraction(self, t: dt.datetime) -> Optional[float]:
        c = self.at(t)
        return None if c is None else 1.0 - c


def _series_from_hourly(hourly: dict, var: str, label: str) -> CloudSeries:
    times = hourly.get("time", [])
    vals = hourly.get(var, [])
    out: Dict[str, float] = {}
    for t, v in zip(times, vals):
        if v is not None:
            out[t] = max(0.0, min(1.0, float(v) / 100.0))
    return CloudSeries(out, label=label)


def _q(site: Site, **params) -> str:
    parts = [f"latitude={site.lat_deg:.4f}", f"longitude={site.lon_deg:.4f}",
             "timezone=UTC"]
    for k, v in params.items():
        parts.append(f"{k}={v}")
    return "&".join(parts)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
def forecast(site: Site, days: int = 16, cache_dir: Optional[str] = None,
             use_cache: bool = False) -> CloudSeries:
    """Operational forecast for the next ``days`` days (max 16).

    Caching is *off* by default here: an operational plan must see fresh data.
    """
    url = f"{FORECAST_API}?{_q(site, hourly='cloud_cover', forecast_days=min(days, 16))}"
    d = _fetch_json(url, cache_dir=cache_dir, use_cache=use_cache)
    return _series_from_hourly(d["hourly"], "cloud_cover", "forecast")


def reanalysis(site: Site, start: dt.date, end: dt.date,
               cache_dir: str = DEFAULT_CACHE_DIR,
               model: str = "era5") -> CloudSeries:
    """ERA5 hourly total cloud cover: the verification truth.

    ``models=era5`` must be pinned explicitly. Left to its default the archive
    endpoint returns a best-match series that, for recent dates, is the archived
    *forecast* itself -- verifying a forecast against it scores the forecast
    against a copy of itself and reports a perfect, meaningless skill of 1.0.
    ERA5 is a reanalysis produced by a separate assimilation cycle, so it is the
    only series here that is genuinely independent of the forecast under test.
    """
    url = (f"{ARCHIVE_API}?{_q(site, hourly='cloud_cover')}"
           f"&start_date={start.isoformat()}&end_date={end.isoformat()}"
           f"&models={model}")
    d = _fetch_json(url, cache_dir=cache_dir)
    return _series_from_hourly(d["hourly"], "cloud_cover", model)


def previous_runs(site: Site, start: dt.date, end: dt.date,
                  lead_days: Iterable[int] = (1, 2, 3, 4, 5, 6, 7),
                  cache_dir: str = DEFAULT_CACHE_DIR) -> Dict[int, CloudSeries]:
    """Forecasts as they were issued 1..7 days before each past timestamp.

    Returns ``{lead_days: CloudSeries}``. Lead 0 is the analysis-time forecast
    and is included under key 0 for reference.
    """
    leads = sorted(set(int(x) for x in lead_days))
    vars_ = ["cloud_cover"] + [f"cloud_cover_previous_day{k}" for k in leads if k >= 1]
    url = (f"{HISTORICAL_FORECAST_API}?{_q(site, hourly=','.join(vars_))}"
           f"&start_date={start.isoformat()}&end_date={end.isoformat()}")
    d = _fetch_json(url, cache_dir=cache_dir)
    hourly = d["hourly"]
    out: Dict[int, CloudSeries] = {
        0: _series_from_hourly(hourly, "cloud_cover", "lead-0")}
    for k in leads:
        if k < 1:
            continue
        var = f"cloud_cover_previous_day{k}"
        if var in hourly:
            out[k] = _series_from_hourly(hourly, var, f"lead-{k}d")
    return out


# ---------------------------------------------------------------------------
# Forecast verification metrics
# ---------------------------------------------------------------------------
def skill_scores(pred: CloudSeries, truth: CloudSeries,
                 clear_threshold: float = 0.30) -> Dict[str, float]:
    """Compare a forecast series against truth on their common timestamps.

    Reports MAE and RMSE on the continuous cloud fraction, plus the contingency
    table of the operational decision that actually matters: "is this hour clear
    enough to observe?".
    """
    keys = sorted(set(pred.values) & set(truth.values))
    if not keys:
        return {"n": 0}
    errs = [pred.values[k] - truth.values[k] for k in keys]
    n = len(keys)
    mae = sum(abs(e) for e in errs) / n
    rmse = (sum(e * e for e in errs) / n) ** 0.5
    bias = sum(errs) / n
    hit = miss = false_alarm = correct_neg = 0
    for k in keys:
        p_clear = pred.values[k] <= clear_threshold
        t_clear = truth.values[k] <= clear_threshold
        if p_clear and t_clear:
            hit += 1
        elif p_clear and not t_clear:
            false_alarm += 1
        elif (not p_clear) and t_clear:
            miss += 1
        else:
            correct_neg += 1
    acc = (hit + correct_neg) / n
    pod = hit / max(hit + miss, 1)                 # probability of detection
    far = false_alarm / max(hit + false_alarm, 1)  # false-alarm ratio
    # Heidke skill score against random chance.
    exp_correct = ((hit + false_alarm) * (hit + miss)
                   + (correct_neg + miss) * (correct_neg + false_alarm)) / n
    hss = (hit + correct_neg - exp_correct) / max(n - exp_correct, 1e-9)
    # Climatological base rate of clear hours, for context.
    base_clear = sum(1 for k in keys if truth.values[k] <= clear_threshold) / n
    return {"n": n, "mae": mae, "rmse": rmse, "bias": bias, "accuracy": acc,
            "pod": pod, "far": far, "hss": hss, "base_clear_rate": base_clear}


@dataclass
class CloudCalibration:
    """Maps a raw forecast cloud fraction to its expected observed value.

    A numerical weather model reports cloud cover as a deterministic field, but
    as a *predictor* it is heavily over-confident: at a monsoon site a forecast
    of 0% cloud is followed on average by around 70% observed cloud. Feeding the
    raw value into a planner therefore makes it bet hard on a signal that is
    mostly noise, and it schedules worse than ignoring weather altogether.

    Least-squares fit of ``E[cloud_true | cloud_forecast] = a + b * c_f``. The
    slope is the honest strength of the signal: b near 1 means the forecast can
    be taken at face value, b near 0 means it carries almost no information and
    the calibrated value collapses to the site climatology, which is exactly the
    behaviour a planner should fall back to.
    """

    intercept: float
    slope: float
    n: int
    correlation: float

    def apply(self, cloud_forecast: float) -> float:
        return max(0.0, min(1.0, self.intercept + self.slope * cloud_forecast))

    def apply_series(self, s: CloudSeries) -> CloudSeries:
        return CloudSeries({k: self.apply(v) for k, v in s.values.items()},
                           label=f"{s.label}-calibrated")

    def as_dict(self) -> Dict[str, float]:
        return {"intercept": self.intercept, "slope": self.slope,
                "n": self.n, "correlation": self.correlation}


def night_hours_filter(lon_deg: float, start_hour: int = 19,
                       end_hour: int = 5):
    """Predicate selecting hour keys that fall in local night.

    Optical observing happens at night, so the calibration must be fitted on
    night hours: cloud regimes and model bias both have a strong diurnal cycle,
    and a fit dominated by daytime hours is being applied out of domain.
    """
    off = dt.timedelta(hours=lon_deg / 15.0)

    def pred(key: str) -> bool:
        h = (dt.datetime.strptime(key, "%Y-%m-%dT%H:%M") + off).hour
        return h >= start_hour or h <= end_hour

    return pred


def fit_calibration(pred: CloudSeries, truth: CloudSeries,
                    hour_filter=None) -> CloudCalibration:
    """Fit the forecast-to-observed mapping on their common timestamps.

    Must be fitted on data that PRECEDES the interval it is applied to; fitting
    and applying on the same interval leaks the answer into the planner.
    ``hour_filter`` restricts the fit to a subset of hours (see
    :func:`night_hours_filter`).
    """
    keys = sorted(set(pred.values) & set(truth.values))
    if hour_filter is not None:
        keys = [k for k in keys if hour_filter(k)]
    n = len(keys)
    if n < 24:
        return CloudCalibration(0.0, 1.0, n, float("nan"))
    xs = [pred.values[k] for k in keys]
    ys = [truth.values[k] for k in keys]
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx <= 0:
        return CloudCalibration(my, 0.0, n, 0.0)
    slope = sxy / sxx
    corr = sxy / ((sxx * syy) ** 0.5) if syy > 0 else 0.0
    return CloudCalibration(my - slope * mx, slope, n, corr)


@dataclass
class ClearProbability:
    """Maps a forecast cloud fraction to P(observed cloud <= threshold).

    :class:`CloudCalibration` answers "how cloudy will it be?", which is the
    right question when value degrades smoothly with cloud. It is the wrong
    question when an observation either succeeds or fails: there, the planner
    needs "how likely is this hour to be usable?", and the two rankings differ.

    Estimated by binning the forecast axis and taking the empirical success rate
    in each bin, shrunk toward the overall base rate in proportion to how little
    data the bin holds (a Beta-style smoothing). Binning avoids assuming any
    functional form, and the shrinkage keeps sparse bins from producing
    confident nonsense.
    """

    edges: List[float]
    probs: List[float]
    base_rate: float
    n: int

    def apply(self, cloud_forecast: float) -> float:
        if not self.probs:
            return self.base_rate
        i = 0
        while i < len(self.edges) and cloud_forecast >= self.edges[i]:
            i += 1
        return self.probs[min(i, len(self.probs) - 1)]

    def as_dict(self) -> Dict:
        return {"edges": self.edges, "probs": [round(p, 4) for p in self.probs],
                "base_rate": round(self.base_rate, 4), "n": self.n}


def fit_clear_probability(pred: CloudSeries, truth: CloudSeries,
                          threshold: float = 0.30, n_bins: int = 10,
                          prior_strength: float = 20.0,
                          hour_filter=None) -> ClearProbability:
    """Fit P(observed cloud <= threshold | forecast cloud) on an earlier window."""
    keys = sorted(set(pred.values) & set(truth.values))
    if hour_filter is not None:
        keys = [k for k in keys if hour_filter(k)]
    n = len(keys)
    if n == 0:
        return ClearProbability([], [], 0.0, 0)
    base = sum(1 for k in keys if truth.values[k] <= threshold) / n

    edges = [(i + 1) / n_bins for i in range(n_bins - 1)]
    counts = [0] * n_bins
    hits = [0] * n_bins
    for k in keys:
        f = pred.values[k]
        b = min(int(f * n_bins), n_bins - 1)
        counts[b] += 1
        if truth.values[k] <= threshold:
            hits[b] += 1
    probs = [(h + prior_strength * base) / (c + prior_strength)
             for h, c in zip(hits, counts)]
    return ClearProbability(edges, probs, base, n)


def persistence_series(truth: CloudSeries, lag_hours: int = 24) -> CloudSeries:
    """Naive baseline: today's sky equals the sky ``lag_hours`` ago."""
    out: Dict[str, float] = {}
    for k, v in truth.values.items():
        t = dt.datetime.strptime(k, "%Y-%m-%dT%H:%M") + dt.timedelta(hours=lag_hours)
        out[hour_key(t)] = v
    return CloudSeries(out, label=f"persistence-{lag_hours}h")


def climatology_series(truth: CloudSeries) -> CloudSeries:
    """Constant-value baseline at the interval's mean cloud fraction."""
    if not truth.values:
        return CloudSeries({}, "climatology")
    m = sum(truth.values.values()) / len(truth.values)
    return CloudSeries({k: m for k in truth.values}, "climatology")
