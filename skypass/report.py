"""Human- and machine-readable output for a plan.

The point of an *integrated* planner is that its output is directly executable,
so the timetable is emitted not only as a table but as an iCalendar file that
drops straight into an observer's calendar, and as CSV for rotator control.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
from typing import Iterable, Optional, Sequence

from .passes import Pass
from .pipeline import PlanResult

COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def compass(az_deg: float) -> str:
    return COMPASS[int((az_deg % 360.0) / 22.5 + 0.5) % 16]


def format_passes(passes: Sequence[Pass], limit: Optional[int] = None,
                  show_score: bool = True) -> str:
    """Fixed-width table of passes."""
    rows = list(passes)[:limit] if limit else list(passes)
    if not rows:
        return "  (no passes)"
    head = (f"{'Satellite':<24}{'AOS (UTC)':<18}{'TCA':<10}{'LOS':<10}"
            f"{'Dur':>6}{'ElMax':>7}{'Az':>6}")
    if show_score:
        head += f"{'Mag':>7}{'Cloud':>7}{'Score':>7}"
    out = [head, "-" * len(head)]
    for p in rows:
        line = (f"{p.name[:23]:<24}{p.aos:%Y-%m-%d %H:%M}  "
                f"{p.tca:%H:%M:%S}  {p.los:%H:%M:%S}  "
                f"{p.duration_s:5.0f}s{p.el_max_deg:6.1f}"
                f"{compass(p.az_tca_deg):>6}")
        if show_score:
            mag = p.detail.get("magnitude")
            cld = p.detail.get("cloud")
            line += (f"{('%.1f' % mag) if mag is not None else '--':>7}"
                     f"{('%.0f%%' % (100 * cld)) if cld is not None else '--':>7}"
                     f"{p.score:7.3f}")
        out.append(line)
    return "\n".join(out)


def format_plan(result: PlanResult, limit: int = 25) -> str:
    """Full operator-facing report for one planning run."""
    f = result.funnel
    sch = result.schedule
    ub = result.upper_bound
    if result.weather_used:
        wx = f"forecast applied ({result.weather_hours} hourly samples)"
    else:
        wx = "NOT applied (weather-blind)"
    pct = (100.0 * sch.objective / ub) if ub else 0.0
    lines = [
        "=" * 78,
        f" SkyPass observation plan - {result.site.name}",
        f" {result.site.lat_deg:+.4f} deg, {result.site.lon_deg:+.4f} deg, "
        f"{result.site.alt_m:.0f} m   mask {result.site.min_elev_deg:.0f} deg   "
        f"mode {result.mode}",
        f" Window {result.t0:%Y-%m-%d %H:%M} -> {result.t1:%Y-%m-%d %H:%M} UTC",
        f" Weather: {wx}",
        "=" * 78,
        "",
        " Visibility funnel",
        f"   element sets in catalogue      {f.catalogue:6d}"
        f"   (+{f.stale_elements} rejected as stale)",
        f"   geometric passes above mask    {f.geometric:6d}",
    ]
    if result.mode == "optical":
        lines += [
            f"     sunlit                       {f.sunlit:6d}",
            f"     and observer in darkness     {f.dark_sky:6d}",
            f"     and brighter than limit      {f.bright_enough:6d}",
        ]
    lines += [
        f"     and forecast cloud < 50%      {f.cloud_clear:6d}"
        f"   (diagnostic; scoring is continuous)",
        f"   candidates above score floor   {f.above_floor:6d}",
        f"   SCHEDULED (conflict-free)      {f.scheduled:6d}",
        "",
        f" Objective {sch.objective:.3f} of {ub:.3f} attainable "
        f"({pct:.1f}% of the conflict-ignoring upper bound)",
        f" Propagations {result.propagations:,}   "
        f"total runtime {result.runtime.get('total', 0.0):.1f} s",
        "",
        " Timetable",
    ]
    lines.append(format_passes(sch.selected if sch else [], limit=limit))
    if sch and sch.count > limit:
        lines.append(f"  ... {sch.count - limit} more")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------
def write_csv(passes: Iterable[Pass], path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    cols = ["name", "norad_id", "aos", "tca", "los", "duration_s", "el_max_deg",
            "az_aos_deg", "az_tca_deg", "az_los_deg", "range_tca_km",
            "magnitude", "cloud", "score", "priority"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for p in passes:
            d = p.to_dict()
            w.writerow([d["name"], d["norad_id"], d["aos"], d["tca"], d["los"],
                        d["duration_s"], d["el_max_deg"], d["az_aos_deg"],
                        d["az_tca_deg"], d["az_los_deg"], d["range_tca_km"],
                        p.detail.get("magnitude", ""), p.detail.get("cloud", ""),
                        d["score"], d["priority"]])
    return path


def _ics_dt(t: dt.datetime) -> str:
    return t.strftime("%Y%m%dT%H%M%SZ")


def write_ics(passes: Iterable[Pass], path: str, site_name: str = "") -> str:
    """iCalendar export, so the timetable is directly actionable."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SkyPass//EN",
           "CALSCALE:GREGORIAN"]
    for i, p in enumerate(passes):
        mag = p.detail.get("magnitude")
        cld = p.detail.get("cloud")
        desc = (f"Max elevation {p.el_max_deg:.1f} deg toward "
                f"{compass(p.az_tca_deg)}\\n"
                f"Rise {compass(p.az_aos_deg)} -> set {compass(p.az_los_deg)}\\n"
                f"Duration {p.duration_s:.0f} s, range at TCA "
                f"{p.range_tca_km:.0f} km\\n"
                + (f"Predicted magnitude {mag:.1f}\\n" if mag is not None else "")
                + (f"Forecast cloud cover {100 * cld:.0f}%\\n" if cld is not None else "")
                + f"SkyPass score {p.score:.3f}")
        out += [
            "BEGIN:VEVENT",
            f"UID:skypass-{p.norad_id}-{_ics_dt(p.tca)}-{i}@skypass",
            f"DTSTAMP:{_ics_dt(now)}",
            f"DTSTART:{_ics_dt(p.aos)}",
            f"DTEND:{_ics_dt(p.los)}",
            f"SUMMARY:{p.name} pass ({p.el_max_deg:.0f} deg)",
            f"LOCATION:{site_name}",
            f"DESCRIPTION:{desc}",
            "END:VEVENT",
        ]
    out.append("END:VCALENDAR")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\r\n".join(out))
    return path


def write_json(result: PlanResult, path: str, include_all: bool = False) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    doc = result.summary()
    doc["schedule"] = result.schedule.to_dict() if result.schedule else None
    if include_all:
        doc["all_passes"] = [p.to_dict() for p in result.passes]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
    return path
