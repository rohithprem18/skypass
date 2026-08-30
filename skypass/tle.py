"""Two-line element acquisition, archiving and hygiene.

SkyPass keeps a dated archive of every element set it downloads. That archive is
what makes the longitudinal experiments (element-set age sensitivity) possible,
and it makes any published prediction reproducible after the fact -- CelesTrak
serves only the *current* elements, so a prediction is otherwise unrepeatable.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from sgp4.api import Satrec

from .config import AMSAT_URL, CELESTRAK_URL, DEFAULT_TLE_GROUPS

USER_AGENT = "SkyPass/1.0 (research; ground-station planning)"


@dataclass
class TleRecord:
    """One element set plus the metadata needed to audit it."""

    name: str
    line1: str
    line2: str
    source: str = "unknown"

    @property
    def norad_id(self) -> int:
        return int(self.line1[2:7])

    @property
    def epoch(self) -> dt.datetime:
        """Element-set epoch decoded from columns 19-32 of line 1."""
        yy = int(self.line1[18:20])
        year = 2000 + yy if yy < 57 else 1900 + yy
        doy = float(self.line1[20:32])
        return (dt.datetime(year, 1, 1)
                + dt.timedelta(days=doy - 1.0))

    def satrec(self) -> Satrec:
        return Satrec.twoline2rv(self.line1, self.line2)

    def age_days(self, t: dt.datetime) -> float:
        return (t - self.epoch).total_seconds() / 86400.0


def _checksum_ok(line: str) -> bool:
    """TLE modulo-10 checksum over columns 1-68 (digits count, '-' counts 1)."""
    if len(line) < 69:
        return False
    total = 0
    for ch in line[:68]:
        if ch.isdigit():
            total += int(ch)
        elif ch == "-":
            total += 1
    return total % 10 == int(line[68])


def parse_tle_text(text: str, source: str = "unknown",
                   verify_checksum: bool = True) -> List[TleRecord]:
    """Parse a 3-line (name/1/2) TLE stream, skipping malformed entries."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    out: List[TleRecord] = []
    i = 0
    while i + 2 < len(lines) + 1:
        if i + 2 >= len(lines):
            break
        name, l1, l2 = lines[i].strip(), lines[i + 1], lines[i + 2]
        if not (l1.startswith("1 ") and l2.startswith("2 ")):
            i += 1                      # resynchronise on a ragged stream
            continue
        i += 3
        if verify_checksum and not (_checksum_ok(l1) and _checksum_ok(l2)):
            continue
        try:
            Satrec.twoline2rv(l1, l2)   # reject sets SGP4 itself will not take
        except Exception:
            continue
        out.append(TleRecord(name=name, line1=l1, line2=l2, source=source))
    return out


def _get(url: str, timeout: float = 45.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_celestrak(groups: Iterable[str] = DEFAULT_TLE_GROUPS,
                    verbose: bool = True) -> List[TleRecord]:
    """Download the configured CelesTrak GP groups."""
    recs: List[TleRecord] = []
    for g in groups:
        url = CELESTRAK_URL.format(group=g)
        try:
            txt = _get(url)
        except Exception as exc:                     # network hiccup on one group
            if verbose:
                print(f"  [warn] group {g!r} failed: {exc}")
            continue
        got = parse_tle_text(txt, source=f"celestrak:{g}")
        if verbose:
            print(f"  celestrak:{g:10s} {len(got):4d} objects")
        recs.extend(got)
    return recs


def fetch_amsat(verbose: bool = True) -> List[TleRecord]:
    """Download the AMSAT 'nasabare' set.

    AMSAT curates its own element sets, so for the same object it usually
    carries a *different epoch* from CelesTrak. That gives us two genuinely
    independent element sets per satellite, which is what the element-set
    sensitivity experiment needs.
    """
    try:
        txt = _get(AMSAT_URL)
    except Exception as exc:
        if verbose:
            print(f"  [warn] AMSAT fetch failed: {exc}")
        return []
    got = parse_tle_text(txt, source="amsat")
    if verbose:
        print(f"  amsat{'':16s}{len(got):4d} objects")
    return got


def dedupe(records: Iterable[TleRecord]) -> Dict[int, TleRecord]:
    """Keep the newest element set per NORAD ID."""
    best: Dict[int, TleRecord] = {}
    for r in records:
        try:
            nid, ep = r.norad_id, r.epoch
        except Exception:
            continue
        cur = best.get(nid)
        if cur is None or ep > cur.epoch:
            best[nid] = r
    return best


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------
def archive_path(archive_dir: str, day: Optional[dt.date] = None) -> str:
    day = day or dt.date.today()
    return os.path.join(archive_dir, f"{day.isoformat()}.txt")


def write_archive(records: Iterable[TleRecord], path: str) -> int:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(f"{r.name}\n{r.line1}\n{r.line2}\n")
            n += 1
    return n


def list_archives(archive_dir: str) -> List[str]:
    if not os.path.isdir(archive_dir):
        return []
    files = [f for f in os.listdir(archive_dir)
             if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.txt", f)]
    return [os.path.join(archive_dir, f) for f in sorted(files)]


def latest_archive(archive_dir: str) -> str:
    files = list_archives(archive_dir)
    if not files:
        raise FileNotFoundError(
            f"no TLE archive in {archive_dir!r} -- run: python -m skypass fetch")
    return files[-1]


def load_archive(path: str) -> List[TleRecord]:
    with open(path, encoding="utf-8") as fh:
        return parse_tle_text(fh.read(), source=os.path.basename(path))


def fresh_records(records: Iterable[TleRecord], t: dt.datetime,
                  max_age_days: float) -> Tuple[List[TleRecord], List[TleRecord]]:
    """Split records into (usable, too-old) by element-set epoch age."""
    ok, stale = [], []
    for r in records:
        try:
            age = r.age_days(t)
        except Exception:
            stale.append(r)
            continue
        (ok if -1.0 <= age <= max_age_days else stale).append(r)
    return ok, stale


def epoch_age_stats(records: Iterable[TleRecord], t: dt.datetime) -> Dict[str, float]:
    ages = []
    for r in records:
        try:
            ages.append(r.age_days(t))
        except Exception:
            pass
    if not ages:
        return {}
    ages.sort()
    n = len(ages)
    return {
        "n": n,
        "mean": sum(ages) / n,
        "median": ages[n // 2],
        "p90": ages[min(n - 1, int(0.90 * n))],
        "max": ages[-1],
    }
