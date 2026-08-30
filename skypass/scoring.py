"""Composite visibility scoring.

A pass is scored in [0, 1] by multiplying a *geometric quality* term by a chain
of independent gating factors. The multiplicative form is deliberate: a pass
that fails any hard requirement (in eclipse, sky still bright, overcast) has to
score zero regardless of how good its geometry is. An additive score cannot
express that, and this is precisely where weather-blind planners go wrong --
they let excellent geometry outvote an overcast sky.

    S = [w_e * f_elev + w_d * f_dur] * f_photometric * f_sky

Two observing modes are supported:

optical
    All terms apply. The object must be sunlit while the observer's sky is dark,
    and it must be brighter than the limiting magnitude.
radio
    Illumination and photometry are irrelevant -- a radio pass works in daylight
    and through cloud. Cloud is still reported (rain fade matters above about
    10 GHz) but by default does not gate the score.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional

from sgp4.api import Satrec

from .config import (DEFAULT_PRIORITY, DEFAULT_PRIORITY_FALLBACK,
                     DEFAULT_STANDARD_MAGNITUDE, STANDARD_MAGNITUDE,
                     ScoreWeights)
from .geometry import (apparent_magnitude, phase_angle, shadow_state,
                       sun_elevation, sun_teme, teme_to_ecef)
from .passes import Pass, Tracker
from .weather import CloudSeries

MODE_OPTICAL = "optical"
MODE_RADIO = "radio"


def standard_magnitude(name: str) -> float:
    """Intrinsic magnitude at 1000 km, by longest matching catalogue key."""
    best_key, best_len = None, -1
    for k in STANDARD_MAGNITUDE:
        if k in name and len(k) > best_len:
            best_key, best_len = k, len(k)
    return STANDARD_MAGNITUDE[best_key] if best_key else DEFAULT_STANDARD_MAGNITUDE


def priority_of(name: str, table: Optional[Dict[str, float]] = None) -> float:
    """Mission-value multiplier, by longest matching key."""
    table = DEFAULT_PRIORITY if table is None else table
    best_key, best_len = None, -1
    for k in table:
        if k in name and len(k) > best_len:
            best_key, best_len = k, len(k)
    return table[best_key] if best_key else DEFAULT_PRIORITY_FALLBACK


@dataclass
class VisibilityReport:
    """Every factor that went into a score, for auditability."""

    score: float = 0.0
    f_elev: float = 0.0
    f_dur: float = 0.0
    f_geom: float = 0.0
    f_mag: float = 1.0
    f_sky: float = 1.0
    sunlit: Optional[bool] = None
    shadow: Optional[str] = None
    observer_dark: Optional[bool] = None
    sun_elev_deg: Optional[float] = None
    magnitude: Optional[float] = None
    phase_deg: Optional[float] = None
    cloud: Optional[float] = None
    rejected: Optional[str] = None

    def as_dict(self) -> Dict:
        d = {k: v for k, v in self.__dict__.items() if v is not None}
        for k in ("score", "f_elev", "f_dur", "f_geom", "f_mag", "f_sky"):
            d[k] = round(d[k], 4)
        for k in ("magnitude", "phase_deg", "sun_elev_deg", "cloud"):
            if k in d:
                d[k] = round(d[k], 3)
        return d


def geometric_quality(p: Pass, w: ScoreWeights) -> tuple:
    """Elevation and duration terms, each saturating at a configured ceiling."""
    f_el = min(max(p.el_max_deg, 0.0) / w.elev_sat_deg, 1.0)
    f_du = min(max(p.duration_s, 0.0) / w.dur_sat_s, 1.0)
    return f_el, f_du, w.w_elev * f_el + w.w_dur * f_du


def score_pass(p: Pass, sat: Satrec, tracker: Tracker,
               clouds: Optional[CloudSeries] = None,
               weights: Optional[ScoreWeights] = None,
               mode: str = MODE_OPTICAL,
               cloud_gates_radio: bool = False,
               weather_aware: bool = True) -> VisibilityReport:
    """Score one pass and return the full factor breakdown.

    ``weather_aware=False`` reproduces a conventional weather-blind planner: the
    cloud factor is computed and reported but not applied. That is the ablation
    the evaluation in the paper turns on.
    """
    w = (weights or ScoreWeights()).normalised()
    rep = VisibilityReport()
    rep.f_elev, rep.f_dur, rep.f_geom = geometric_quality(p, w)
    s = rep.f_geom

    apex = tracker.observe(sat, p.tca)
    if apex is None:
        rep.rejected = "propagation_error"
        return rep

    if mode == MODE_OPTICAL:
        r_sun_teme = sun_teme(apex.jd, apex.fr)
        rep.shadow = shadow_state(apex.r_teme, r_sun_teme)
        rep.sunlit = rep.shadow != "umbra"
        rep.sun_elev_deg = sun_elevation(tracker.site, tracker.obs_ecef, p.tca)
        rep.observer_dark = rep.sun_elev_deg < tracker.site.twilight_deg

        if not rep.sunlit:
            rep.rejected = "eclipsed"
            return rep
        if not rep.observer_dark:
            rep.rejected = "daylight"
            return rep

        r_sun_ecef = teme_to_ecef(r_sun_teme, apex.jd, apex.fr)
        r_sat_ecef = teme_to_ecef(apex.r_teme, apex.jd, apex.fr)
        psi = phase_angle(r_sat_ecef, tracker.obs_ecef, r_sun_ecef)
        rep.phase_deg = math.degrees(psi)
        rep.magnitude = apparent_magnitude(standard_magnitude(p.name),
                                           apex.range_km, psi)
        span = max(w.mag_limit - w.mag_bright, 1e-9)
        rep.f_mag = max(w.mag_floor,
                        min(1.0, (w.mag_limit - rep.magnitude) / span))
        if rep.magnitude > w.mag_limit:
            rep.rejected = "too_faint"
            rep.score = 0.0
            return rep
        s *= rep.f_mag

    # --- sky-condition gate -------------------------------------------------
    if clouds is not None:
        c = clouds.at(p.tca)
        rep.cloud = c
        if c is not None:
            rep.f_sky = max(0.0, 1.0 - c) ** w.cloud_exponent
            applies = weather_aware and (mode == MODE_OPTICAL or cloud_gates_radio)
            if applies:
                s *= rep.f_sky

    rep.score = s
    return rep


def apply_scores(passes, sats: Dict[int, Satrec], tracker: Tracker,
                 clouds: Optional[CloudSeries] = None,
                 weights: Optional[ScoreWeights] = None,
                 mode: str = MODE_OPTICAL,
                 weather_aware: bool = True,
                 priority_table: Optional[Dict[str, float]] = None):
    """Score a list of passes in place; returns the same list."""
    for p in passes:
        sat = sats.get(p.norad_id)
        if sat is None:
            p.score, p.detail = 0.0, {"rejected": "no_element_set"}
            continue
        rep = score_pass(p, sat, tracker, clouds=clouds, weights=weights,
                         mode=mode, weather_aware=weather_aware)
        p.score = rep.score
        p.priority = priority_of(p.name, priority_table)
        p.detail = rep.as_dict()
    return passes
