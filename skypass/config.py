"""Configuration objects for SkyPass.

Everything that a ground-station operator would want to change lives here as a
dataclass, so experiments can instantiate several sites/weightings side by side
instead of mutating module-level globals.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Tuple

# ---------------------------------------------------------------------------
# Physical constants (WGS-84 / IAU)
# ---------------------------------------------------------------------------
WGS84_A_KM = 6378.137
WGS84_F = 1.0 / 298.257223563
WGS84_B_KM = WGS84_A_KM * (1.0 - WGS84_F)
AU_KM = 149_597_870.7
SUN_RADIUS_KM = 696_000.0


@dataclass(frozen=True)
class Site:
    """A ground station."""

    name: str
    lat_deg: float
    lon_deg: float
    alt_m: float = 0.0
    #: Horizon mask. Passes never rising above this are discarded outright.
    min_elev_deg: float = 10.0
    #: Observer solar elevation below which the sky is dark enough for optical
    #: work. -6 deg = civil twilight, -12 nautical, -18 astronomical.
    twilight_deg: float = -6.0
    #: Antenna slew / instrument reconfiguration time between two observations.
    setup_gap_min: float = 5.0

    def with_(self, **kw) -> "Site":
        return replace(self, **kw)


@dataclass(frozen=True)
class ScoreWeights:
    """Weights of the additive geometric term of the visibility score.

    ``w_elev + w_dur`` should equal 1; :meth:`normalised` enforces it.
    """

    w_elev: float = 0.5
    w_dur: float = 0.5
    #: Elevation (deg) at which the elevation term saturates at 1.0.
    elev_sat_deg: float = 60.0
    #: Duration (s) at which the duration term saturates at 1.0.
    dur_sat_s: float = 480.0
    #: Faintest magnitude still considered detectable (score -> 0 there).
    mag_limit: float = 6.0
    #: Brightest magnitude mapped to a photometric factor of 1.0.
    mag_bright: float = 0.0
    #: Floor of the photometric factor, so a faint-but-geometrically-superb
    #: pass is not annihilated.
    mag_floor: float = 0.10
    #: Exponent on the clear-sky fraction (1 - cloud). >1 punishes cloud harder.
    cloud_exponent: float = 1.0

    def normalised(self) -> "ScoreWeights":
        s = self.w_elev + self.w_dur
        if s <= 0:
            raise ValueError("score weights must sum to a positive number")
        return replace(self, w_elev=self.w_elev / s, w_dur=self.w_dur / s)


@dataclass(frozen=True)
class PlannerConfig:
    """Numerical settings of the pass-finding and scheduling stages."""

    #: Coarse elevation-sampling step (s) used to bracket horizon crossings.
    coarse_step_s: float = 30.0
    #: Bisection / golden-section convergence tolerance (s).
    tol_s: float = 0.1
    #: Passes scoring below this are never scheduled.
    score_floor: float = 0.05
    #: Cloud fraction above which a pass is reported as "clouded out".
    cloud_cutoff: float = 0.50
    #: Reject an element set whose epoch is older than this (days).
    #: Measured degradation (experiments/exp8_tle_age.py) puts mean culmination
    #: error at 0.05 s inside a day, 0.47 s at 5-7 days, but 4.3 s at 7-14 --
    #: enough to miss the start of a short pass. 7 days is the point beyond
    #: which the elements, not the algorithm, set the achievable accuracy.
    max_tle_age_days: float = 7.0


# ---------------------------------------------------------------------------
# Catalogue metadata
# ---------------------------------------------------------------------------
#: Standard magnitude = visual magnitude at 1000 km range, fully illuminated.
#: Values follow the widely used McCants/Mike McCants intrinsic-magnitude
#: convention distributed with quicksat; unlisted objects fall back to DEFAULT.
STANDARD_MAGNITUDE: Dict[str, float] = {
    "ISS (ZARYA)": -1.8,
    "ISS (NAUKA)": -1.8,
    "CSS (TIANHE)": -1.0,
    "TIANGONG": -1.0,
    "HST": 1.5,
    "NOAA 15": 4.3,
    "NOAA 18": 4.3,
    "NOAA 19": 4.3,
    "METEOR-M2": 4.5,
    "METEOR-M2 2": 4.5,
    "METEOR-M2 3": 4.5,
    "METEOR-M2 4": 4.5,
    "METOP-B": 4.0,
    "METOP-C": 4.0,
    "TERRA": 3.5,
    "AQUA": 3.5,
    "SUOMI NPP": 4.0,
    "NOAA 20": 4.0,
    "NOAA 21": 4.0,
    "FENGYUN 3D": 4.5,
    "COSMOS 2221": 3.5,
    "SL-16 R/B": 3.0,
}
DEFAULT_STANDARD_MAGNITUDE = 5.0

#: Mission-value multiplier applied to the visibility score before scheduling.
#: Matched as a case-sensitive substring of the object name; longest match wins.
DEFAULT_PRIORITY: Dict[str, float] = {
    "ISS": 2.0,
    "CSS": 1.8,
    "NOAA": 1.5,
    "METEOR": 1.4,
    "METOP": 1.3,
    "HST": 1.3,
}
DEFAULT_PRIORITY_FALLBACK = 1.0

#: CelesTrak GP groups fetched by ``skypass fetch``.
DEFAULT_TLE_GROUPS: Tuple[str, ...] = (
    "stations",     # crewed platforms
    "visual",       # the 100 brightest objects -- the optical observer core
    "weather",      # NOAA / METEOR / METOP APT and HRPT downlinks
    "amateur",      # amateur-radio payloads
    "science",
    "resource",     # Earth-resources imagers
    "cubesat",
    "engineering",
)

CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=TLE"
AMSAT_URL = "https://www.amsat.org/tle/current/nasabare.txt"


# ---------------------------------------------------------------------------
# Ground stations used in the multi-site evaluation (Sec. V-E of the paper).
# Chosen to span distinct cloud climatologies, from arid to equatorial monsoon.
# ---------------------------------------------------------------------------
GROUND_STATIONS: Dict[str, Site] = {
    "chennai": Site("Chennai, India", 12.92, 80.12, 30.0),
    "bengaluru": Site("Bengaluru, India", 12.97, 77.59, 920.0),
    "leh": Site("Leh, India", 34.16, 77.58, 3500.0),
    "tucson": Site("Tucson, USA", 32.22, -110.97, 728.0),
    "singapore": Site("Singapore", 1.35, 103.82, 15.0),
    "reykjavik": Site("Reykjavik, Iceland", 64.13, -21.90, 30.0),
    "svalbard": Site("Svalbard, Norway", 78.23, 15.39, 450.0),
}

DEFAULT_SITE = GROUND_STATIONS["chennai"]
