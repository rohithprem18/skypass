"""Shared plumbing for the experiment scripts."""
from __future__ import annotations

import datetime as dt
import json
import os
import platform
import sys
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skypass.paths import (  # noqa: E402  (needs the sys.path line above)
    FIGURES_DIR as FIG_DIR,
    RESULTS_DIR,
    TLE_ARCHIVE_DIR as ARCHIVE_DIR,
)


def save(name: str, payload: Dict) -> str:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    payload = dict(payload)
    payload["_meta"] = environment()
    path = os.path.join(RESULTS_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    print(f"\n  -> {path}")
    return path


def load(name: str) -> Dict:
    with open(os.path.join(RESULTS_DIR, f"{name}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def environment() -> Dict:
    import sgp4
    return {
        "generated_utc": dt.datetime.now(dt.timezone.utc).replace(
            microsecond=0).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "sgp4_version": getattr(sgp4, "__version__", "unknown"),
    }


def banner(title: str) -> None:
    print()
    print("=" * 74)
    print(f" {title}")
    print("=" * 74)


def stats(values: List[float]) -> Dict[str, float]:
    """Mean / median / p95 / max of a sample, plus its size."""
    v = sorted(x for x in values if x is not None)
    n = len(v)
    if n == 0:
        return {"n": 0}
    mean = sum(v) / n
    var = sum((x - mean) ** 2 for x in v) / n
    return {
        "n": n,
        "mean": mean,
        "std": var ** 0.5,
        "median": v[n // 2],
        "p95": v[min(n - 1, int(0.95 * n))],
        "max": v[-1],
    }


def fmt(d: Dict[str, float], keys=("mean", "median", "p95", "max"),
        prec: int = 3) -> str:
    return "  ".join(f"{k}={d[k]:.{prec}f}" for k in keys if k in d)


def past_window(days: int, end_offset_days: int = 6):
    """A verification window that ends far enough back for ERA5 to be final.

    ERA5 lags real time by about five days, so an evaluation interval must stop
    before that or the truth series comes back short.
    """
    end = dt.date.today() - dt.timedelta(days=end_offset_days)
    return end - dt.timedelta(days=days - 1), end
