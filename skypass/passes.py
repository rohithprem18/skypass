"""Pass extraction: coarse bracketing, bisection refinement, apex search.

The cost of pass prediction is dominated by calls to the SGP4 propagator, so the
whole design goal here is to spend as few of them as possible while still
locating acquisition-of-signal (AOS), time of closest approach (TCA) and
loss-of-signal (LOS) to sub-second precision.

Strategy
--------
1. Sample elevation on a coarse grid (default 30 s) to *bracket* every horizon
   crossing. Elevation is smooth and unimodal within a pass, so a sign change of
   ``el - mask`` between adjacent samples brackets exactly one crossing.
2. Refine each bracketed crossing by bisection to a 0.1 s tolerance -- about 8
   extra propagations for a 30 s bracket, versus the 30 propagations that 1 s
   dense sampling would spend on the same interval at 1 s resolution only.
3. Locate TCA by golden-section search on the bracketed unimodal apex.

The coarse step is the one real risk: too coarse and a short grazing pass can
slip between two samples. :func:`adaptive_coarse_step` therefore ties the step
to the orbital period rather than leaving it a fixed constant.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from sgp4.api import Satrec

from .config import PlannerConfig, Site
from .geometry import (Vec3, ecef_to_topocentric, site_ecef, teme_to_ecef)
from .timeutil import jd_of


class PropagationCounter:
    """Counts SGP4 evaluations so experiments can quantify the saving."""

    def __init__(self) -> None:
        self.calls = 0

    def reset(self) -> None:
        self.calls = 0

    def tick(self) -> None:
        self.calls += 1


@dataclass
class Observation:
    """Instantaneous look angles of one object from one site."""

    t: dt.datetime
    az_deg: float
    el_deg: float
    range_km: float
    r_teme: Vec3
    jd: float
    fr: float


@dataclass
class Pass:
    """One horizon-to-horizon transit above the site's elevation mask."""

    name: str
    norad_id: int
    aos: dt.datetime
    tca: dt.datetime
    los: dt.datetime
    el_max_deg: float
    az_aos_deg: float = 0.0
    az_tca_deg: float = 0.0
    az_los_deg: float = 0.0
    range_tca_km: float = 0.0
    #: True when AOS or LOS is a window edge rather than a real horizon
    #: crossing. Always-up objects (geostationary, very high orbits) produce
    #: only clipped "passes", whose AOS/TCA/LOS carry no physical meaning and
    #: must be excluded from any timing statistic.
    clipped: bool = False
    # Filled in by the scoring stage.
    score: float = 0.0
    priority: float = 1.0
    detail: Dict = field(default_factory=dict)

    @property
    def duration_s(self) -> float:
        return (self.los - self.aos).total_seconds()

    @property
    def value(self) -> float:
        """Objective contribution used by the scheduler."""
        return self.score * self.priority

    def key(self) -> Tuple[int, str]:
        return (self.norad_id, self.tca.strftime("%Y%m%d%H%M"))

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "norad_id": self.norad_id,
            "aos": self.aos.isoformat(),
            "tca": self.tca.isoformat(),
            "los": self.los.isoformat(),
            "duration_s": round(self.duration_s, 2),
            "el_max_deg": round(self.el_max_deg, 3),
            "az_aos_deg": round(self.az_aos_deg, 1),
            "az_tca_deg": round(self.az_tca_deg, 1),
            "az_los_deg": round(self.az_los_deg, 1),
            "range_tca_km": round(self.range_tca_km, 1),
            "clipped": self.clipped,
            "score": round(self.score, 4),
            "priority": self.priority,
            "detail": self.detail,
        }


class Tracker:
    """Binds one site to one element set and answers look-angle queries."""

    def __init__(self, site: Site, counter: Optional[PropagationCounter] = None):
        self.site = site
        self.obs_ecef = site_ecef(site)
        self.counter = counter or PropagationCounter()

    def observe(self, sat: Satrec, t: dt.datetime) -> Optional[Observation]:
        jd, fr = jd_of(t)
        err, r, _v = sat.sgp4(jd, fr)
        self.counter.tick()
        if err != 0:
            return None
        r_ecef = teme_to_ecef(r, jd, fr)
        az, el, rng = ecef_to_topocentric(r_ecef, self.site, self.obs_ecef)
        return Observation(t=t, az_deg=az, el_deg=el, range_km=rng,
                           r_teme=r, jd=jd, fr=fr)

    def elevation(self, sat: Satrec, t: dt.datetime) -> Optional[float]:
        o = self.observe(sat, t)
        return None if o is None else o.el_deg


def orbital_period_s(sat: Satrec) -> float:
    """Keplerian period from the SGP4 mean motion (rad/min)."""
    if sat.no_kozai <= 0:
        return 5400.0
    return 2.0 * math.pi / sat.no_kozai * 60.0


def adaptive_coarse_step(sat: Satrec, base_step_s: float,
                         samples_per_orbit: int = 240) -> float:
    """Coarse step tied to the orbital period, capped by the configured step.

    240 samples per orbit puts roughly 20 samples inside a typical LEO pass, so
    even a short grazing transit is bracketed. Slower (higher) orbits get a
    proportionally longer step, which is where most of the saving comes from.
    """
    p = orbital_period_s(sat)
    return max(5.0, min(base_step_s, p / samples_per_orbit))


def _bisect_crossing(tracker: Tracker, sat: Satrec, t_lo: dt.datetime,
                     t_hi: dt.datetime, mask: float, rising: bool,
                     tol_s: float) -> dt.datetime:
    """Refine the instant at which elevation crosses the mask.

    Invariant on entry: ``(el(t_lo) >= mask) != (el(t_hi) >= mask)``.
    """
    lo, hi = t_lo, t_hi
    while (hi - lo).total_seconds() > tol_s:
        mid = lo + (hi - lo) / 2
        el = tracker.elevation(sat, mid)
        if el is None:
            return mid
        if (el >= mask) == rising:
            hi = mid
        else:
            lo = mid
    return lo + (hi - lo) / 2


_INV_PHI = (math.sqrt(5.0) - 1.0) / 2.0


def _golden_apex(tracker: Tracker, sat: Satrec, t_lo: dt.datetime,
                 t_hi: dt.datetime, tol_s: float
                 ) -> Tuple[dt.datetime, Optional[Observation]]:
    """Golden-section maximisation of elevation on a unimodal bracket."""
    a, b = t_lo, t_hi

    def at(frac_from_a: float) -> dt.datetime:
        return a + dt.timedelta(seconds=frac_from_a * (b - a).total_seconds())

    c = at(1.0 - _INV_PHI)
    d = at(_INV_PHI)
    fc = tracker.elevation(sat, c)
    fd = tracker.elevation(sat, d)
    while (b - a).total_seconds() > tol_s:
        if (fc if fc is not None else -90.0) > (fd if fd is not None else -90.0):
            b, d, fd = d, c, fc
            span = (b - a).total_seconds()
            c = a + dt.timedelta(seconds=(1.0 - _INV_PHI) * span)
            fc = tracker.elevation(sat, c)
        else:
            a, c, fc = c, d, fd
            span = (b - a).total_seconds()
            d = a + dt.timedelta(seconds=_INV_PHI * span)
            fd = tracker.elevation(sat, d)
    tca = a + (b - a) / 2
    return tca, tracker.observe(sat, tca)


def find_passes(tracker: Tracker, sat: Satrec, name: str, norad_id: int,
                t0: dt.datetime, t1: dt.datetime,
                cfg: Optional[PlannerConfig] = None,
                step_s: Optional[float] = None,
                adaptive: bool = True) -> List[Pass]:
    """All passes above the site's mask in ``[t0, t1)``.

    Passes already in progress at ``t0`` or still in progress at ``t1`` are
    clipped to the window and reported; their AOS/LOS are then window edges, not
    true horizon crossings.
    """
    cfg = cfg or PlannerConfig()
    mask = tracker.site.min_elev_deg
    if step_s is None:
        step_s = (adaptive_coarse_step(sat, cfg.coarse_step_s) if adaptive
                  else cfg.coarse_step_s)
    step = dt.timedelta(seconds=step_s)

    out: List[Pass] = []
    t = t0
    el_prev = tracker.elevation(sat, t)
    started_above = el_prev is not None and el_prev >= mask
    aos: Optional[dt.datetime] = t if started_above else None
    open_is_clipped = started_above

    while t < t1:
        t_next = min(t + step, t1)
        el_next = tracker.elevation(sat, t_next)
        if el_prev is not None and el_next is not None:
            if el_prev < mask <= el_next:                       # rising edge
                aos = _bisect_crossing(tracker, sat, t, t_next, mask,
                                       rising=True, tol_s=cfg.tol_s)
            elif el_prev >= mask > el_next and aos is not None:  # setting edge
                los = _bisect_crossing(tracker, sat, t, t_next, mask,
                                       rising=False, tol_s=cfg.tol_s)
                out.append(_assemble(tracker, sat, name, norad_id, aos, los,
                                     cfg, clipped=open_is_clipped))
                aos = None
                open_is_clipped = False
        if t_next == t1:
            break
        t, el_prev = t_next, el_next

    if aos is not None and aos < t1:                             # clipped at t1
        out.append(_assemble(tracker, sat, name, norad_id, aos, t1, cfg,
                             clipped=True))
    return out


def _assemble(tracker: Tracker, sat: Satrec, name: str, norad_id: int,
              aos: dt.datetime, los: dt.datetime,
              cfg: PlannerConfig, clipped: bool = False) -> Pass:
    tca, apex = _golden_apex(tracker, sat, aos, los, cfg.tol_s)
    o_aos = tracker.observe(sat, aos)
    o_los = tracker.observe(sat, los)
    return Pass(
        name=name,
        norad_id=norad_id,
        aos=aos, tca=tca, los=los,
        el_max_deg=apex.el_deg if apex else 0.0,
        az_aos_deg=o_aos.az_deg if o_aos else 0.0,
        az_tca_deg=apex.az_deg if apex else 0.0,
        az_los_deg=o_los.az_deg if o_los else 0.0,
        range_tca_km=apex.range_km if apex else 0.0,
        clipped=clipped,
    )


def find_passes_dense(tracker: Tracker, sat: Satrec, name: str, norad_id: int,
                      t0: dt.datetime, t1: dt.datetime,
                      step_s: float = 1.0,
                      mask: Optional[float] = None) -> List[Pass]:
    """Reference implementation: uniform dense sampling, no refinement.

    This is the brute-force baseline the fast path is measured against. AOS/LOS
    resolution is exactly ``step_s`` and TCA is the best grid sample, so with
    ``step_s = 1`` the answers are correct to about 1 s and 0.5 s respectively.
    """
    mask = tracker.site.min_elev_deg if mask is None else mask
    step = dt.timedelta(seconds=step_s)
    out: List[Pass] = []
    t = t0
    cur: List[Observation] = []
    first = True
    while t < t1:
        o = tracker.observe(sat, t)
        if o is not None and o.el_deg >= mask:
            cur.append(o)
        elif cur:
            out.append(_from_samples(cur, name, norad_id,
                                     clipped=first and cur[0].t == t0))
            cur = []
            first = False
        t += step
    if cur:
        out.append(_from_samples(cur, name, norad_id, clipped=True))
    return out


def _from_samples(samples: List[Observation], name: str, norad_id: int,
                  clipped: bool = False) -> Pass:
    apex = max(samples, key=lambda o: o.el_deg)
    return Pass(
        name=name, norad_id=norad_id,
        aos=samples[0].t, tca=apex.t, los=samples[-1].t,
        el_max_deg=apex.el_deg,
        az_aos_deg=samples[0].az_deg,
        az_tca_deg=apex.az_deg,
        az_los_deg=samples[-1].az_deg,
        range_tca_km=apex.range_km,
        clipped=clipped,
    )


def match_passes(a: List[Pass], b: List[Pass], tol_s: float = 300.0
                 ) -> List[Tuple[Pass, Pass]]:
    """Pair passes from two lists by nearest TCA, within ``tol_s``.

    Greedy nearest-neighbour matching; both lists are short and time-ordered, so
    a full assignment solve would not change the result.
    """
    pairs: List[Tuple[Pass, Pass]] = []
    used = set()
    for pa in a:
        best, best_dt = None, None
        for j, pb in enumerate(b):
            if j in used:
                continue
            d = abs((pa.tca - pb.tca).total_seconds())
            if d <= tol_s and (best_dt is None or d < best_dt):
                best, best_dt, best_j = pb, d, j
        if best is not None:
            used.add(best_j)
            pairs.append((pa, best))
    return pairs
