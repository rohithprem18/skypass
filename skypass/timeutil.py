"""Time-scale helpers.

SkyPass works internally in naive UTC ``datetime`` objects; this module is the
only place that converts them to the Julian-date pair that ``sgp4`` expects and
to Greenwich sidereal time.
"""
from __future__ import annotations

import datetime as dt
import math
from typing import Tuple

from sgp4.api import jday

DEG = math.pi / 180.0


def utcnow() -> dt.datetime:
    """Current UTC as a naive ``datetime`` truncated to whole seconds."""
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0, tzinfo=None)


def as_naive_utc(t: dt.datetime) -> dt.datetime:
    """Strip a tz-aware datetime down to naive UTC (no-op if already naive)."""
    if t.tzinfo is None:
        return t
    return t.astimezone(dt.timezone.utc).replace(tzinfo=None)


def jd_of(t: dt.datetime) -> Tuple[float, float]:
    """Split Julian date (day, fraction) of a naive-UTC datetime."""
    t = as_naive_utc(t)
    return jday(t.year, t.month, t.day, t.hour, t.minute,
                t.second + t.microsecond * 1e-6)


def gmst_rad(jd: float, fr: float) -> float:
    """Greenwich mean sidereal time in radians (IAU 1982 series).

    Accurate to well under an arcsecond over the decades of interest, which is
    two orders of magnitude finer than the SGP4 error budget.
    """
    d = (jd - 2451545.0) + fr
    T = d / 36525.0
    g = (280.46061837
         + 360.98564736629 * d
         + 0.000387933 * T * T
         - T * T * T / 38_710_000.0)
    return (g % 360.0) * DEG


def hour_key(t: dt.datetime) -> str:
    """The ``YYYY-MM-DDTHH:00`` key used to index hourly weather series."""
    return as_naive_utc(t).strftime("%Y-%m-%dT%H:00")
