"""The integrated planning pipeline.

This is the contribution that the separate modules exist to support: one call
that takes a site and a horizon and returns an executable, conflict-free,
weather-aware observation timetable, together with the funnel statistics that
explain how many passes were lost at each stage and why.
"""
from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from sgp4.api import Satrec

from .config import (DEFAULT_SITE, PlannerConfig, ScoreWeights, Site)
from .passes import Pass, PropagationCounter, Tracker, find_passes
from .scheduler import Schedule, optimal_schedule
from .scoring import MODE_OPTICAL, apply_scores
from .tle import TleRecord, fresh_records, latest_archive, load_archive
from .timeutil import utcnow
from .weather import CloudSeries, WeatherUnavailable, forecast


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
         verbose: bool = False) -> PlanResult:
    """Run the full pipeline: elements -> passes -> scores -> timetable."""
    cfg = cfg or PlannerConfig()
    weights = weights or ScoreWeights()
    t0 = t0 or utcnow()
    t1 = t0 + dt.timedelta(days=days)
    timing: Dict[str, float] = {}

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

    # 3. Propagation and pass extraction ----------------------------------
    tic = time.perf_counter()
    counter = PropagationCounter()
    tracker = Tracker(site, counter)
    passes, sats = propagate_all(records, tracker, t0, t1, cfg)
    timing["propagate"] = time.perf_counter() - tic

    # 4. Scoring -----------------------------------------------------------
    tic = time.perf_counter()
    apply_scores(passes, sats, tracker, clouds=clouds, weights=weights,
                 mode=mode, weather_aware=weather_aware)
    timing["score"] = time.perf_counter() - tic

    # 5. Conflict resolution ----------------------------------------------
    tic = time.perf_counter()
    candidates = [p for p in passes if p.score >= cfg.score_floor]
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
                      runtime=timing, propagations=counter.calls)
