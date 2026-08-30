"""Frame transformations, topocentric geometry, solar position and photometry.

Nothing here depends on SGP4: the propagator hands us a TEME position vector and
this module turns it into what an observer actually cares about -- azimuth,
elevation, range, whether the object is in sunlight, and how bright it looks.
"""
from __future__ import annotations

import datetime as dt
import math
from typing import Tuple

from .config import AU_KM, SUN_RADIUS_KM, WGS84_A_KM, WGS84_F, Site
from .timeutil import DEG, gmst_rad, jd_of

Vec3 = Tuple[float, float, float]

_E2 = WGS84_F * (2.0 - WGS84_F)


# ---------------------------------------------------------------------------
# Vector helpers
# ---------------------------------------------------------------------------
def dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(a: Vec3) -> float:
    return math.sqrt(dot(a, a))


def sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a: Vec3, k: float) -> Vec3:
    return (a[0] * k, a[1] * k, a[2] * k)


def unit(a: Vec3) -> Vec3:
    n = norm(a)
    return scale(a, 1.0 / n) if n else (0.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------
def teme_to_ecef(r: Vec3, jd: float, fr: float) -> Vec3:
    """Rotate TEME to ECEF about the pole by GMST.

    Polar motion (below 0.5 arcsec, i.e. under 15 m at the surface) is
    neglected; it sits far below the SGP4 along-track error and does not affect
    pass timing at the 0.1 s level.
    """
    th = gmst_rad(jd, fr)
    c, s = math.cos(th), math.sin(th)
    return (c * r[0] + s * r[1], -s * r[0] + c * r[1], r[2])


def site_ecef(site: Site) -> Vec3:
    """Geodetic (lat, lon, alt) to geocentric ECEF position in km (WGS-84)."""
    la, lo = site.lat_deg * DEG, site.lon_deg * DEG
    h = site.alt_m / 1000.0
    n = WGS84_A_KM / math.sqrt(1.0 - _E2 * math.sin(la) ** 2)
    return ((n + h) * math.cos(la) * math.cos(lo),
            (n + h) * math.cos(la) * math.sin(lo),
            (n * (1.0 - _E2) + h) * math.sin(la))


def ecef_to_topocentric(r_ecef: Vec3, site: Site, obs_ecef: Vec3):
    """Return (azimuth deg, elevation deg, slant range km) of an ECEF point.

    Elevation is geometric; no refraction is applied (see :func:`refracted`).
    """
    d = sub(r_ecef, obs_ecef)
    la, lo = site.lat_deg * DEG, site.lon_deg * DEG
    sl, cl = math.sin(la), math.cos(la)
    so, co = math.sin(lo), math.cos(lo)
    east = -so * d[0] + co * d[1]
    north = -sl * co * d[0] - sl * so * d[1] + cl * d[2]
    up = cl * co * d[0] + cl * so * d[1] + sl * d[2]
    rng = math.sqrt(east * east + north * north + up * up)
    if rng == 0.0:
        return 0.0, 90.0, 0.0
    el = math.asin(max(-1.0, min(1.0, up / rng))) / DEG
    az = (math.atan2(east, north) / DEG) % 360.0
    return az, el, rng


def refracted(el_deg: float) -> float:
    """Apparent elevation including standard atmospheric refraction.

    Bennett (1982) for 1010 mbar / 10 C. Used only for reporting: the horizon
    mask itself is applied to the geometric elevation, so results stay
    reproducible independently of assumed surface conditions.
    """
    if el_deg < -1.0:
        return el_deg
    r_arcmin = 1.0 / math.tan((el_deg + 7.31 / (el_deg + 4.4)) * DEG)
    return el_deg + r_arcmin / 60.0


# ---------------------------------------------------------------------------
# Solar position and illumination
# ---------------------------------------------------------------------------
def sun_teme(jd: float, fr: float) -> Vec3:
    """Low-precision geocentric solar position (km), mean equinox of date.

    Accuracy about 0.01 deg, which is ample: the quantities it feeds
    (Earth-shadow entry and observer twilight) have tolerances of order 0.1 deg.
    """
    n = (jd - 2451545.0) + fr
    L = (280.460 + 0.9856474 * n) % 360.0
    g = ((357.528 + 0.9856003 * n) % 360.0) * DEG
    lam = (L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) * DEG
    eps = (23.439 - 3.6e-7 * n) * DEG
    r = (1.00014 - 0.01671 * math.cos(g) - 0.00014 * math.cos(2 * g)) * AU_KM
    return (r * math.cos(lam),
            r * math.cos(eps) * math.sin(lam),
            r * math.sin(eps) * math.sin(lam))


def shadow_state(r_sat: Vec3, r_sun: Vec3) -> str:
    """Conical Earth-shadow test: "sunlit", "penumbra" or "umbra".

    Standard dual-cone construction (Vallado, *Fundamentals of Astrodynamics
    and Applications*, Sec. 5.3): compare the satellite angular offset from the
    anti-solar direction against the umbral and penumbral cone half-angles. The
    cylindrical shadow used by many amateur predictors misplaces eclipse entry
    by several seconds in low Earth orbit.
    """
    r_mag = norm(r_sat)
    s_mag = norm(r_sun)
    if r_mag == 0.0 or s_mag == 0.0:
        return "sunlit"
    # Angle between the satellite radius vector and the anti-solar direction.
    cos_theta = -dot(r_sat, r_sun) / (r_mag * s_mag)
    cos_theta = max(-1.0, min(1.0, cos_theta))
    theta = math.acos(cos_theta)
    if theta >= math.pi / 2.0:
        return "sunlit"                      # sunward hemisphere
    # Distance along the shadow axis and perpendicular offset from it.
    d_axis = r_mag * math.cos(theta)
    d_perp = r_mag * math.sin(theta)
    # Umbral cone: apex beyond the Earth on the anti-solar side.
    x_u = WGS84_A_KM * s_mag / max(SUN_RADIUS_KM - WGS84_A_KM, 1e-9)
    alpha_u = math.asin(min(1.0, WGS84_A_KM / x_u))
    r_umbra = (x_u - d_axis) * math.tan(alpha_u)
    if d_perp < r_umbra:
        return "umbra"
    # Penumbral cone: apex between the Earth and the Sun.
    x_p = WGS84_A_KM * s_mag / max(SUN_RADIUS_KM + WGS84_A_KM, 1e-9)
    alpha_p = math.asin(min(1.0, WGS84_A_KM / x_p))
    r_penumbra = (x_p + d_axis) * math.tan(alpha_p)
    if d_perp < r_penumbra:
        return "penumbra"
    return "sunlit"


def is_sunlit(r_sat: Vec3, r_sun: Vec3) -> bool:
    """True when the object receives direct sunlight (penumbra counts)."""
    return shadow_state(r_sat, r_sun) != "umbra"


def sun_elevation(site: Site, obs_ecef: Vec3, t: dt.datetime) -> float:
    """Solar elevation at the site in degrees; negative after sunset."""
    jd, fr = jd_of(t)
    s_ecef = teme_to_ecef(sun_teme(jd, fr), jd, fr)
    return ecef_to_topocentric(s_ecef, site, obs_ecef)[1]


# ---------------------------------------------------------------------------
# Photometry
# ---------------------------------------------------------------------------
def phase_angle(r_sat_ecef: Vec3, obs_ecef: Vec3, r_sun_ecef: Vec3) -> float:
    """Sun-object-observer angle in radians (0 = fully illuminated face)."""
    to_sun = unit(sub(r_sun_ecef, r_sat_ecef))
    to_obs = unit(sub(obs_ecef, r_sat_ecef))
    return math.acos(max(-1.0, min(1.0, dot(to_sun, to_obs))))


def diffuse_sphere_phase(psi: float) -> float:
    """Normalised phase function of a Lambertian sphere, 1.0 at opposition.

    p(psi) = (2/3pi)[(pi - psi) cos psi + sin psi], divided by p(0) = 2/3.
    """
    p = (2.0 / (3.0 * math.pi)) * ((math.pi - psi) * math.cos(psi) + math.sin(psi))
    return max(p / (2.0 / 3.0), 1e-6)


def apparent_magnitude(std_mag: float, range_km: float, psi: float) -> float:
    """Visual magnitude from a standard magnitude defined at 1000 km, phase 0.

    m = m_std + 5 log10(d / 1000 km) - 2.5 log10 F(psi)
    """
    d = max(range_km, 1.0)
    return std_mag + 5.0 * math.log10(d / 1000.0) - 2.5 * math.log10(
        diffuse_sphere_phase(psi))
