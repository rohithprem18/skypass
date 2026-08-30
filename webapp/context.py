"""Observing context the planner computes but did not previously publish.

The planner's job ends at a schedule. An observation *console* needs the things
that surround a schedule: when the sky is actually dark, how the cloud field
moves across the night, which nights are worth spending a budget on, and which
passes lost a conflict to which. All of it is derived from the same ``skypass``
package the paper validates -- nothing is re-implemented here, so the interface
still cannot drift from the published results.
"""
from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional, Sequence

from skypass.config import Site
from skypass.geometry import shadow_state, site_ecef, sun_elevation, sun_teme
from skypass.scheduler import observing_night
from skypass.timeutil import hour_key

#: Solar elevations that bound the conventional twilight phases, darkest first.
#: Astronomical twilight (-18 deg) is the point beyond which the sky no longer
#: brightens, which is what actually limits faint optical work.
TWILIGHT_BANDS = (
    ("day", 0.0),
    ("civil", -6.0),
    ("nautical", -12.0),
    ("astronomical", -18.0),
)


def _crossings(site: Site, obs, t0: dt.datetime, t1: dt.datetime,
               threshold: float, step_min: int = 5) -> List[Dict]:
    """Times the solar elevation crosses ``threshold``, by sign of the change.

    Sampled coarsely then bisected: the sun moves slowly enough that a 5-minute
    bracket followed by a few halvings lands within a second, and the whole
    night costs a few hundred analytic sun positions rather than a search.
    """
    out: List[Dict] = []
    step = dt.timedelta(minutes=step_min)
    t = t0
    prev_t, prev_v = t0, sun_elevation(site, obs, t0) - threshold
    while t < t1:
        t = min(t + step, t1)
        v = sun_elevation(site, obs, t) - threshold
        if prev_v == 0 or (prev_v < 0) != (v < 0):
            lo, hi = prev_t, t
            for _ in range(20):                      # ~0.3 s resolution
                mid = lo + (hi - lo) / 2
                if (sun_elevation(site, obs, mid) - threshold < 0) == (prev_v < 0):
                    lo = mid
                else:
                    hi = mid
            out.append({"t": (lo + (hi - lo) / 2).isoformat(timespec="seconds"),
                        "falling": v < prev_v})
        prev_t, prev_v = t, v
    return out


def twilight(site: Site, t0: dt.datetime, t1: dt.datetime) -> Dict[str, List[Dict]]:
    """Every twilight crossing in the window, keyed by phase name.

    A polar site can go a whole window without the sun crossing a threshold at
    all; the empty list that results is the correct answer, and the interface
    reads it as "this band never opens" rather than as missing data.
    """
    obs = site_ecef(site)
    return {name: _crossings(site, obs, t0, t1, deg)
            for name, deg in TWILIGHT_BANDS}


def darkness_windows(site: Site, t0: dt.datetime, t1: dt.datetime,
                     threshold: Optional[float] = None) -> List[Dict]:
    """Intervals the planner itself counts as dark.

    The threshold defaults to the site's own ``twilight_deg`` rather than to
    astronomical twilight, because that is the value the scoring stage tests
    against. Drawing a stricter band than the planner used puts scheduled
    passes outside their own darkness, which reads as a bug in the schedule
    when it is really a mismatch of definitions.
    """
    if threshold is None:
        threshold = site.twilight_deg
    obs = site_ecef(site)
    marks = _crossings(site, obs, t0, t1, threshold)
    dark = sun_elevation(site, obs, t0) < threshold
    out, start = [], t0 if dark else None
    for m in marks:
        t = dt.datetime.fromisoformat(m["t"])
        if m["falling"]:
            start = t
        elif start is not None:
            out.append({"from": start.isoformat(timespec="seconds"),
                        "to": t.isoformat(timespec="seconds")})
            start = None
    if start is not None:
        out.append({"from": start.isoformat(timespec="seconds"),
                    "to": t1.isoformat(timespec="seconds")})
    return out


def twilight_bands(site: Site, t0: dt.datetime,
                   t1: dt.datetime) -> Dict[str, List[Dict]]:
    """Nested intervals for each twilight phase, lightest to darkest.

    Each band is the interval the sun spends below that phase's threshold, so
    the bands nest: astronomical sits inside nautical, which sits inside civil.
    Drawn in that order they render as a graded ramp from dusk to full dark
    without any of them having to know about the others.
    """
    return {name: darkness_windows(site, t0, t1, threshold=deg)
            for name, deg in TWILIGHT_BANDS}


def hourly_cloud(clouds, t0: dt.datetime, t1: dt.datetime) -> List[Dict]:
    """The cloud field as the forecast actually publishes it: hour by hour.

    Per-pass cloud answers "will I see this one"; the hourly series answers
    "when does the night clear", which is the question that decides whether to
    set up at all.
    """
    if clouds is None:
        return []
    out = []
    t = t0.replace(minute=0, second=0, microsecond=0)
    while t <= t1:
        v = clouds.values.get(hour_key(t))
        if v is not None:
            out.append({"t": t.isoformat(timespec="seconds"), "cloud": round(v, 3)})
        t += dt.timedelta(hours=1)
    return out


def night_summaries(candidates: Sequence, selected: Sequence,
                    lon_deg: float) -> List[Dict]:
    """One row per observing night: the unit a budget is actually spent in.

    exp4 is the reason this exists. Weather-awareness pays when the observer can
    move effort *between* nights, so the interface has to make nights, not
    passes, the thing being compared.
    """
    chosen = {(p.norad_id, p.aos) for p in selected}
    nights: Dict[str, Dict] = {}
    for p in candidates:
        key = observing_night(p, lon_deg).isoformat()
        n = nights.setdefault(key, {"night": key, "passes": 0, "selected": 0,
                                    "_cloud": [], "best_el": 0.0,
                                    "best_score": 0.0})
        n["passes"] += 1
        if (p.norad_id, p.aos) in chosen:
            n["selected"] += 1
        c = (p.detail or {}).get("cloud")
        if c is not None:
            n["_cloud"].append(c)
        n["best_el"] = max(n["best_el"], p.el_max_deg)
        n["best_score"] = max(n["best_score"], p.score)

    rows = []
    for n in sorted(nights.values(), key=lambda x: x["night"]):
        cl = n.pop("_cloud")
        n["cloud"] = round(sum(cl) / len(cl), 3) if cl else None
        n["best_el"] = round(n["best_el"], 1)
        n["best_score"] = round(n["best_score"], 3)
        rows.append(n)

    # "Best" is the night the scheduler actually favoured, broken by forecast.
    ranked = [r for r in rows if r["selected"] > 0]
    if ranked:
        best = max(ranked, key=lambda r: (r["selected"],
                                          -(r["cloud"] if r["cloud"] is not None else 1.0),
                                          r["best_score"]))
        for r in rows:
            r["verdict"] = ("best" if r is best
                            else "good" if r["selected"] > 0 else "skip")
    else:
        for r in rows:
            r["verdict"] = "skip"
    return rows


def conflict_map(candidates: Sequence, selected: Sequence,
                 gap_min: float) -> Dict[int, List[Dict]]:
    """For each unselected candidate, the scheduled pass whose slot it wanted.

    This is what turns the scheduler from a black box into something an
    observer can argue with: not "score 0.74" but "it lost to ISS, which was
    13 degrees higher and under less cloud".
    """
    gap = dt.timedelta(minutes=gap_min)
    chosen = {(p.norad_id, p.aos) for p in selected}
    out: Dict[int, List[Dict]] = {}
    for c in candidates:
        if (c.norad_id, c.aos) in chosen:
            continue
        for s in selected:
            if c.aos < s.los + gap and s.aos < c.los + gap:
                out.setdefault(c.norad_id, []).append({
                    "norad_id": s.norad_id, "name": s.name,
                    "aos": s.aos.isoformat(timespec="seconds"),
                })
    return out


def sunlit_fraction(tracker, sat, p, n: int = 12) -> Optional[float]:
    """Share of the pass the object spends out of Earth's shadow.

    A pass that enters eclipse at culmination is worthless optically even
    though its geometry looks ideal, so the fraction is worth reporting
    alongside the elevation rather than folded silently into the score.
    """
    if sat is None:
        return None
    total = (p.los - p.aos).total_seconds()
    if total <= 0:
        return None
    lit = seen = 0
    for i in range(n + 1):
        o = tracker.observe(sat, p.aos + dt.timedelta(seconds=total * i / n))
        if o is None:
            continue
        seen += 1
        # Penumbra still counts: the object is dimmed, not dark.
        if shadow_state(o.r_teme, sun_teme(o.jd, o.fr)) != "umbra":
            lit += 1
    return round(lit / seen, 3) if seen else None
