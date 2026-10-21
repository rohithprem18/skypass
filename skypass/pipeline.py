"""The integrated planning pipeline.

This is the contribution that the separate modules exist to support: one call
that takes a site and a horizon and returns an executable, conflict-free,
weather-aware observation timetable, together with the funnel statistics that
explain how many passes were lost at each stage and why.
"""
from __future__ import annotations

import datetime as dt
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from sgp4.api import Satrec

from .config import (DEFAULT_SITE, PlannerConfig, ScoreWeights, Site)
from .passes import Pass, PropagationCounter, Tracker, find_passes
from .scheduler import (Schedule, budget_schedule, capacity_schedule,
                        optimal_schedule)
from .scoring import MODE_OPTICAL, apply_scores
from .tle import TleRecord, fresh_records, latest_archive, load_archive
from .timeutil import as_naive_utc, hour_key, utcnow
from .weather import (MIN_CALIBRATION_HOURS, CloudCalibration, CloudSeries,
                      WeatherUnavailable, forecast, site_calibration)


@dataclass
class Funnel:
    """How many passes survive each successive constraint."""

    catalogue: int = 0
    stale_elements: int = 0
    geometric: int = 0
    sunlit: int = 0
    dark_sky: int = 0
    bright_enough: int = 0
    cloud_clear: int = 0
    above_floor: int = 0
    scheduled: int = 0

    def as_dict(self) -> Dict[str, int]:
        return dict(self.__dict__)


@dataclass
class PlanResult:
    """Everything a run produces, ready to serialise."""

    site: Site
    t0: dt.datetime
    t1: dt.datetime
    mode: str
    passes: List[Pass] = field(default_factory=list)
    candidates: List[Pass] = field(default_factory=list)
    schedule: Optional[Schedule] = None
    funnel: Funnel = field(default_factory=Funnel)
    weather_used: bool = False
    weather_hours: int = 0
    #: The forecast calibration applied before scoring, or None when the raw
    #: forecast was used (``calibrate=False``, weather-blind, or no fit).
    calibration: Optional[CloudCalibration] = None
    capacity: Optional[int] = None
    budget: Optional[int] = None
    runtime: Dict[str, float] = field(default_factory=dict)
    propagations: int = 0

    @property
    def upper_bound(self) -> float:
        """Sum of all candidate values: the value of an infeasible plan that
        somehow observed every candidate. Used to normalise schedule quality."""
        return sum(p.value for p in self.candidates)

    def summary(self) -> Dict:
        sch = self.schedule
        return {
            "site": self.site.name,
            "lat_deg": self.site.lat_deg,
            "lon_deg": self.site.lon_deg,
            "t0": self.t0.isoformat(),
            "t1": self.t1.isoformat(),
            "horizon_days": round((self.t1 - self.t0).total_seconds() / 86400.0, 2),
            "mode": self.mode,
            "weather_used": self.weather_used,
            "weather_hours": self.weather_hours,
            "calibrated": self.calibration is not None,
            "calibration": (self.calibration.as_dict()
                            if self.calibration else None),
            "capacity_per_night": self.capacity,
            "window_budget": self.budget,
            "algorithm": sch.algorithm if sch else "",
            "funnel": self.funnel.as_dict(),
            "objective": round(sch.objective, 4) if sch else 0.0,
            "upper_bound": round(self.upper_bound, 4),
            "scheduled": sch.count if sch else 0,
            "propagations": self.propagations,
            "runtime": {k: round(v, 3) for k, v in self.runtime.items()},
        }


def load_catalogue(archive_dir: str = "tle_archive",
                   path: Optional[str] = None,
                   t: Optional[dt.datetime] = None,
                   cfg: Optional[PlannerConfig] = None,
                   limit: Optional[int] = None,
                   name_filter: Optional[str] = None):
    """Load element sets, drop stale ones, and return (records, stale_count)."""
    cfg = cfg or PlannerConfig()
    t = t or utcnow()
    recs = load_archive(path or latest_archive(archive_dir))
    if name_filter:
        needles = [s.strip().upper() for s in name_filter.split(",") if s.strip()]
        recs = [r for r in recs if any(nd in r.name.upper() for nd in needles)]
    ok, stale = fresh_records(recs, t, cfg.max_tle_age_days)
    if limit:
        ok = ok[:limit]
    return ok, len(stale)


def propagate_all(records: Sequence[TleRecord], tracker: Tracker,
                  t0: dt.datetime, t1: dt.datetime,
                  cfg: Optional[PlannerConfig] = None):
    """Find every geometric pass for every element set. Returns (passes, sats)."""
    cfg = cfg or PlannerConfig()
    passes: List[Pass] = []
    sats: Dict[int, Satrec] = {}
    for r in records:
        try:
            sat = r.satrec()
        except Exception:
            continue
        sats[r.norad_id] = sat
        try:
            passes.extend(find_passes(tracker, sat, r.name, r.norad_id,
                                      t0, t1, cfg))
        except Exception:
            continue                       # a single bad element set must not
                                           # abort a 600-object catalogue
    passes.sort(key=lambda p: p.aos)
    return passes, sats


def plan(site: Site = DEFAULT_SITE,
         days: float = 7.0,
         t0: Optional[dt.datetime] = None,
         mode: str = MODE_OPTICAL,
         weather_aware: bool = True,
         clouds: Optional[CloudSeries] = None,
         fetch_weather: bool = True,
         weights: Optional[ScoreWeights] = None,
         cfg: Optional[PlannerConfig] = None,
         archive_dir: str = "tle_archive",
         tle_path: Optional[str] = None,
         limit: Optional[int] = None,
         name_filter: Optional[str] = None,
         records: Optional[Sequence[TleRecord]] = None,
         scheduler=optimal_schedule,
         calibrate: bool = True,
         calibration: Optional[CloudCalibration] = None,
         capacity: Optional[int] = None,
         budget: Optional[int] = None,
         nowcast: Optional[float] = None,
         nowcast_hours: float = 1.0,
         verbose: bool = False) -> PlanResult:
    """Run the full pipeline: elements -> passes -> scores -> timetable.

    By default the cloud forecast is calibrated against ERA5 before scoring
    (:func:`skypass.weather.site_calibration`), the configuration the paper
    evaluates; ``calibrate=False`` scores the raw forecast. A prefitted
    ``calibration`` is used as given instead of being fitted.

    Scheduling follows the observing constraints supplied:

    * neither ``capacity`` nor ``budget``: ``scheduler`` (default
      :func:`optimal_schedule`, unlimited observations);
    * ``capacity`` K only: at most K observations per observing night
      (:func:`capacity_schedule`), a fixed nightly quota;
    * ``budget`` N: at most N observations over the whole horizon with at most
      ``capacity`` (default ``cfg.nightly_capacity``) per night
      (:func:`budget_schedule`). Only this mode lets the station skip a cloudy
      night, which is where the forecast adds value.
    """
    cfg = cfg or PlannerConfig()
    weights = weights or ScoreWeights()
    t0 = t0 or utcnow()
    t1 = t0 + dt.timedelta(days=days)
    timing: Dict[str, float] = {}
    if capacity is not None and capacity < 1:
        raise ValueError(f"capacity must be >= 1, got {capacity}")
    if budget is not None and budget < 1:
        raise ValueError(f"budget must be >= 1, got {budget}")
    if budget is not None and capacity is None:
        capacity = cfg.nightly_capacity

    # 1. Element sets ------------------------------------------------------
    tic = time.perf_counter()
    if records is None:
        records, n_stale = load_catalogue(archive_dir, tle_path, t0, cfg,
                                          limit, name_filter)
    else:
        records, n_stale = list(records), 0
    timing["load_tle"] = time.perf_counter() - tic

    # 2. Weather -----------------------------------------------------------
    tic = time.perf_counter()
    if clouds is None and weather_aware and fetch_weather:
        try:
            # +1 day of headroom: a pass whose TCA falls just past midnight of
            # the last horizon day must still find a cloud sample.
            clouds = forecast(site, days=int(min(16, max(1, days + 1))))
        except WeatherUnavailable as exc:
            if verbose:
                print(f"  [warn] weather unavailable, continuing blind: {exc}")
            clouds = None
    timing["weather"] = time.perf_counter() - tic

    # 2b. Forecast calibration --------------------------------------------
    # The raw model cloud field is over-confident; scoring it directly is the
    # configuration the experiments find worse than ignoring weather under a
    # nightly quota. Map it to E[observed cloud | forecast] first.
    tic = time.perf_counter()
    scored_clouds = clouds
    applied: Optional[CloudCalibration] = None
    if clouds is not None and weather_aware and calibrate:
        if calibration is None:
            try:
                calibration = site_calibration(
                    site, as_naive_utc(t0).date(),
                    train_days=cfg.calibration_train_days,
                    lead_days=cfg.calibration_lead_days)
            except WeatherUnavailable as exc:
                if verbose:
                    print(f"  [warn] calibration data unavailable, "
                          f"scoring the raw forecast: {exc}")
                calibration = None
        if calibration is not None and calibration.n >= MIN_CALIBRATION_HOURS:
            applied = calibration
            scored_clouds = calibration.apply_series(clouds)
        elif calibration is not None and verbose:
            print(f"  [warn] only {calibration.n} calibration hours, "
                  f"scoring the raw forecast")
    # 2c. Sky-camera nowcast ------------------------------------------------
    # An observed cloud fraction (skypass.ml.cloudcam) is a measurement, not a
    # forecast, so it replaces the calibrated values for the next
    # ``nowcast_hours`` instead of being calibrated itself. This is the
    # sub-hourly signal the forecast lacks within a night.
    if nowcast is not None and weather_aware:
        if not 0.0 <= nowcast <= 1.0:
            raise ValueError(f"nowcast must be a cloud fraction in [0, 1], got {nowcast}")
        base = dict(scored_clouds.values) if scored_clouds is not None else {}
        start = as_naive_utc(t0).replace(minute=0, second=0, microsecond=0)
        for h in range(int(math.ceil(nowcast_hours)) + 1):
            base[hour_key(start + dt.timedelta(hours=h))] = float(nowcast)
        scored_clouds = CloudSeries(base, label="nowcast+forecast")
    timing["calibrate"] = time.perf_counter() - tic

    # 3. Propagation and pass extraction ----------------------------------
    tic = time.perf_counter()
    counter = PropagationCounter()
    tracker = Tracker(site, counter)
    passes, sats = propagate_all(records, tracker, t0, t1, cfg)
    timing["propagate"] = time.perf_counter() - tic

    # 4. Scoring -----------------------------------------------------------
    tic = time.perf_counter()
    apply_scores(passes, sats, tracker, clouds=scored_clouds, weights=weights,
                 mode=mode, weather_aware=weather_aware)
    if applied is not None:
        # ``cloud`` is the calibrated value the score used; keep the forecast
        # as issued alongside it so a reader can see what the model said.
        for p in passes:
            if p.detail.get("cloud") is not None:
                p.detail["cloud_raw"] = round(clouds.at(p.tca), 3)
    timing["score"] = time.perf_counter() - tic

    # 5. Conflict resolution ----------------------------------------------
    tic = time.perf_counter()
    candidates = [p for p in passes if p.score >= cfg.score_floor]
    if budget is not None:
        sched = budget_schedule(candidates, site.setup_gap_min, capacity,
                                budget, lon_deg=site.lon_deg)
    elif capacity is not None:
        sched = capacity_schedule(candidates, site.setup_gap_min,
                                  capacity=capacity, per_night=True,
                                  lon_deg=site.lon_deg)
    else:
        sched = scheduler(candidates, site.setup_gap_min)
    timing["schedule"] = time.perf_counter() - tic
    timing["total"] = sum(timing.values())

    # 6. Funnel accounting -------------------------------------------------
    f = Funnel(catalogue=len(records), stale_elements=n_stale,
               geometric=len(passes))
    for p in passes:
        d = p.detail
        if mode == MODE_OPTICAL:
            if not d.get("sunlit"):
                continue
            f.sunlit += 1
            if not d.get("observer_dark"):
                continue
            f.dark_sky += 1
            if d.get("rejected") == "too_faint":
                continue
            f.bright_enough += 1
        else:
            f.sunlit = f.dark_sky = f.bright_enough = len(passes)
        c = d.get("cloud")
        if c is None or c < cfg.cloud_cutoff:
            f.cloud_clear += 1
    f.above_floor = len(candidates)
    f.scheduled = sched.count

    return PlanResult(site=site, t0=t0, t1=t1, mode=mode, passes=passes,
                      candidates=candidates, schedule=sched, funnel=f,
                      weather_used=clouds is not None and weather_aware,
                      weather_hours=len(clouds) if clouds else 0,
                      calibration=applied, capacity=capacity, budget=budget,
                      runtime=timing, propagations=counter.calls)
