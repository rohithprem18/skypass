"""Unit tests. Run with:  python -m pytest tests -q   (or: python tests/test_skypass.py)

The scheduler tests matter most: they check the dynamic program against
exhaustive search on thousands of randomised instances, which is the only way to
be confident an O(n log n) optimum really is the optimum.
"""
from __future__ import annotations

import datetime as dt
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skypass.config import GROUND_STATIONS, PlannerConfig, ScoreWeights, Site
from skypass.geometry import (apparent_magnitude, diffuse_sphere_phase,
                              ecef_to_topocentric, is_sunlit, refracted,
                              shadow_state, site_ecef, sun_teme)
from skypass.passes import (Pass, Tracker, adaptive_coarse_step, find_passes,
                            find_passes_dense, match_passes)
from skypass.scheduler import (brute_force_budget, brute_force_capacity,
                               brute_force_optimal, budget_schedule,
                               capacity_schedule, genetic_schedule,
                               greedy_budget, greedy_highest_value,
                               greedy_max_elevation, observing_night,
                               optimal_schedule)
from skypass.scoring import priority_of, standard_magnitude
from skypass.timeutil import gmst_rad, jd_of
from skypass.tle import TleRecord, parse_tle_text
from skypass.weather import CloudSeries, skill_scores

T0 = dt.datetime(2026, 8, 29, 0, 0, 0)

# A real ISS element set, used as a fixed fixture so tests do not need network.
ISS_L1 = "1 25544U 98067A   24274.52916667  .00016717  00000-0  30074-3 0  9990"
ISS_L2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49814641    46"


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def test_site_ecef_radius():
    """Geocentric radius must lie between the polar and equatorial radii."""
    for key, site in GROUND_STATIONS.items():
        r = math.dist((0, 0, 0), site_ecef(site))
        assert 6350.0 < r < 6390.0, (key, r)


def test_site_ecef_equator_and_pole():
    eq = site_ecef(Site("eq", 0.0, 0.0, 0.0))
    assert abs(eq[0] - 6378.137) < 1e-6 and abs(eq[2]) < 1e-9
    pole = site_ecef(Site("pole", 90.0, 0.0, 0.0))
    assert abs(pole[2] - 6356.752) < 1e-3


def test_topocentric_zenith():
    """A point straight up must read 90 deg elevation at any latitude."""
    for lat in (-70.0, 0.0, 12.92, 78.0):
        s = Site("t", lat, 45.0, 0.0)
        o = site_ecef(s)
        # Geodetic "up" is normal to the ellipsoid, NOT parallel to the
        # geocentric radius vector; the two differ by up to ~0.19 deg.
        la, lo = math.radians(lat), math.radians(45.0)
        u = (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))
        up = tuple(o[i] + 500.0 * u[i] for i in range(3))
        az, el, rng = ecef_to_topocentric(up, s, o)
        assert abs(el - 90.0) < 1e-6
        assert abs(rng - 500.0) < 1.0


def test_topocentric_cardinal_azimuth():
    """Displacing north of the site must give azimuth 0, east must give 90."""
    s = Site("t", 0.0, 0.0, 0.0)
    o = site_ecef(s)
    north = (o[0], o[1], o[2] + 100.0)
    east = (o[0], o[1] + 100.0, o[2])
    assert abs(ecef_to_topocentric(north, s, o)[0] - 0.0) < 1e-6
    assert abs(ecef_to_topocentric(east, s, o)[0] - 90.0) < 1e-6


def test_gmst_monotonic_and_period():
    """GMST advances by slightly more than 2 pi in one solar day."""
    jd, fr = jd_of(T0)
    a = gmst_rad(jd, fr)
    b = gmst_rad(jd + 1.0, fr)
    d = (b - a) % (2 * math.pi)
    assert d < 0.02 or d > 2 * math.pi - 0.02   # ~ +236 s of sidereal drift


def test_shadow_states():
    sun = (1.496e8, 0.0, 0.0)
    assert shadow_state((7000.0, 0.0, 0.0), sun) == "sunlit"
    assert shadow_state((-7000.0, 0.0, 0.0), sun) == "umbra"
    # Well off the shadow axis on the anti-solar side: still sunlit.
    assert shadow_state((-7000.0, 9000.0, 0.0), sun) == "sunlit"
    assert is_sunlit((7000.0, 0.0, 0.0), sun)


def test_penumbra_between_umbra_and_sunlight():
    """Sweeping off-axis must cross umbra -> penumbra -> sunlit, in order."""
    sun = (1.496e8, 0.0, 0.0)
    states = [shadow_state((-7000.0, y, 0.0), sun) for y in range(0, 9000, 50)]
    first_pen = states.index("penumbra")
    first_sun = states.index("sunlit")
    assert 0 < first_pen < first_sun
    assert all(s == "umbra" for s in states[:first_pen])


def test_phase_function_bounds():
    assert abs(diffuse_sphere_phase(0.0) - 1.0) < 1e-9
    assert diffuse_sphere_phase(math.pi / 2) < 0.4
    assert diffuse_sphere_phase(math.pi) < 1e-4
    # Monotonically decreasing with phase angle.
    vals = [diffuse_sphere_phase(x) for x in
            [i * math.pi / 20 for i in range(21)]]
    assert all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))


def test_magnitude_inverse_square():
    """Doubling range must dim the object by 5 log10(2) = 1.505 mag."""
    m1 = apparent_magnitude(2.0, 500.0, 0.0)
    m2 = apparent_magnitude(2.0, 1000.0, 0.0)
    assert abs((m2 - m1) - 5.0 * math.log10(2.0)) < 1e-9
    # At 1000 km, phase 0, the apparent magnitude IS the standard magnitude.
    assert abs(apparent_magnitude(2.0, 1000.0, 0.0) - 2.0) < 1e-9


def test_refraction_raises_and_shrinks_with_altitude():
    assert refracted(0.0) > 0.0
    assert refracted(10.0) - 10.0 > refracted(45.0) - 45.0 > 0.0


def test_sun_distance_is_about_one_au():
    jd, fr = jd_of(T0)
    r = math.dist((0, 0, 0), sun_teme(jd, fr))
    assert 1.45e8 < r < 1.53e8


# ---------------------------------------------------------------------------
# TLE parsing
# ---------------------------------------------------------------------------
def test_parse_and_epoch():
    recs = parse_tle_text(f"ISS (ZARYA)\n{ISS_L1}\n{ISS_L2}\n")
    assert len(recs) == 1
    r = recs[0]
    assert r.norad_id == 25544
    assert r.epoch.year == 2024 and r.epoch.month == 9 and r.epoch.day == 30
    assert r.age_days(dt.datetime(2024, 10, 1, 12, 42)) > 0.0


def test_parse_rejects_bad_checksum():
    bad = ISS_L1[:-1] + ("0" if ISS_L1[-1] != "0" else "1")
    assert parse_tle_text(f"ISS\n{bad}\n{ISS_L2}\n") == []
    assert len(parse_tle_text(f"ISS\n{bad}\n{ISS_L2}\n",
                              verify_checksum=False)) == 1


def test_parse_resynchronises_on_junk():
    txt = f"# header junk\nISS (ZARYA)\n{ISS_L1}\n{ISS_L2}\n"
    assert len(parse_tle_text(txt)) == 1


# ---------------------------------------------------------------------------
# Pass extraction
# ---------------------------------------------------------------------------
def _iss():
    return TleRecord("ISS (ZARYA)", ISS_L1, ISS_L2).satrec()


def test_adaptive_step_respects_cap_and_period():
    sat = _iss()
    s = adaptive_coarse_step(sat, 30.0)
    assert 5.0 <= s <= 30.0


def test_fast_matches_dense_sampling():
    """The headline accuracy claim, as a test: bisection must agree with a
    1 s dense scan to well under a second on AOS/TCA/LOS."""
    site = GROUND_STATIONS["chennai"].with_(min_elev_deg=10.0)
    t0 = dt.datetime(2024, 10, 1, 0, 0, 0)
    t1 = t0 + dt.timedelta(days=1)
    sat = _iss()
    fast = find_passes(Tracker(site), sat, "ISS", 25544, t0, t1, PlannerConfig())
    dense = find_passes_dense(Tracker(site), sat, "ISS", 25544, t0, t1, step_s=1.0)
    pairs = match_passes(fast, dense)
    assert len(pairs) >= 3
    assert len(pairs) == len(dense)          # no pass was missed
    for a, b in pairs:
        assert abs((a.aos - b.aos).total_seconds()) < 1.0
        assert abs((a.los - b.los).total_seconds()) < 1.0
        assert abs((a.tca - b.tca).total_seconds()) < 2.0
        assert abs(a.el_max_deg - b.el_max_deg) < 0.05


def test_fast_uses_far_fewer_propagations():
    site = GROUND_STATIONS["chennai"]
    t0 = dt.datetime(2024, 10, 1, 0, 0, 0)
    t1 = t0 + dt.timedelta(days=1)
    tf, td = Tracker(site), Tracker(site)
    find_passes(tf, _iss(), "ISS", 25544, t0, t1, PlannerConfig())
    find_passes_dense(td, _iss(), "ISS", 25544, t0, t1, step_s=1.0)
    assert td.counter.calls > 10 * tf.counter.calls


def test_pass_ordering_and_duration():
    site = GROUND_STATIONS["chennai"]
    t0 = dt.datetime(2024, 10, 1, 0, 0, 0)
    ps = find_passes(Tracker(site), _iss(), "ISS", 25544, t0,
                     t0 + dt.timedelta(days=2), PlannerConfig())
    assert ps
    for p in ps:
        assert p.aos < p.tca < p.los
        assert p.duration_s > 0
        assert p.el_max_deg >= site.min_elev_deg - 0.01
    for i in range(len(ps) - 1):
        assert ps[i].los <= ps[i + 1].aos


def test_higher_mask_yields_fewer_shorter_passes():
    t0 = dt.datetime(2024, 10, 1, 0, 0, 0)
    t1 = t0 + dt.timedelta(days=2)
    low = find_passes(Tracker(GROUND_STATIONS["chennai"].with_(min_elev_deg=5.0)),
                      _iss(), "ISS", 25544, t0, t1, PlannerConfig())
    high = find_passes(Tracker(GROUND_STATIONS["chennai"].with_(min_elev_deg=30.0)),
                       _iss(), "ISS", 25544, t0, t1, PlannerConfig())
    assert len(high) <= len(low)
    if high:
        assert (sum(p.duration_s for p in high) / len(high)
                < sum(p.duration_s for p in low) / len(low))


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------
def test_longest_key_wins_for_magnitude_and_priority():
    assert standard_magnitude("ISS (ZARYA)") == -1.8
    assert standard_magnitude("NOAA 19") == 4.3
    assert standard_magnitude("SOMETHING UNKNOWN") == 5.0
    assert priority_of("ISS (ZARYA)") == 2.0
    assert priority_of("NOAA 19") == 1.5
    assert priority_of("RANDOM DEBRIS") == 1.0


def test_weights_normalise():
    w = ScoreWeights(w_elev=3.0, w_dur=1.0).normalised()
    assert abs(w.w_elev - 0.75) < 1e-12 and abs(w.w_dur - 0.25) < 1e-12


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------
def test_cloud_series_interpolates():
    cs = CloudSeries({"2026-08-29T10:00": 0.0, "2026-08-29T11:00": 1.0})
    assert cs.at(dt.datetime(2026, 8, 29, 10, 0)) == 0.0
    assert abs(cs.at(dt.datetime(2026, 8, 29, 10, 30)) - 0.5) < 1e-9
    assert cs.at(dt.datetime(2026, 8, 29, 11, 0)) == 1.0
    assert cs.at(dt.datetime(2026, 8, 29, 9, 0)) is None
    assert abs(cs.clear_fraction(dt.datetime(2026, 8, 29, 10, 30)) - 0.5) < 1e-9


def test_skill_scores_perfect_forecast():
    truth = CloudSeries({f"2026-08-29T{h:02d}:00": (h % 5) / 4.0 for h in range(24)})
    s = skill_scores(truth, truth)
    assert s["mae"] == 0.0 and s["rmse"] == 0.0
    assert abs(s["accuracy"] - 1.0) < 1e-12
    assert abs(s["hss"] - 1.0) < 1e-9


def test_skill_scores_detect_bias():
    truth = CloudSeries({f"2026-08-29T{h:02d}:00": 0.2 for h in range(24)})
    pred = CloudSeries({f"2026-08-29T{h:02d}:00": 0.5 for h in range(24)})
    s = skill_scores(pred, truth)
    assert abs(s["bias"] - 0.3) < 1e-9
    assert abs(s["mae"] - 0.3) < 1e-9


# ---------------------------------------------------------------------------
# Scheduling -- the core correctness claim
# ---------------------------------------------------------------------------
def _mkpass(start_min: float, dur_min: float, value: float, i: int = 0) -> Pass:
    aos = T0 + dt.timedelta(minutes=start_min)
    los = aos + dt.timedelta(minutes=dur_min)
    p = Pass(name=f"SAT{i}", norad_id=i, aos=aos,
             tca=aos + (los - aos) / 2, los=los, el_max_deg=10.0 + value)
    p.score, p.priority = value, 1.0
    return p


def _random_instance(rng: random.Random, n: int):
    out = []
    for i in range(n):
        start = rng.uniform(0, 240)
        dur = rng.uniform(2, 15)
        out.append(_mkpass(start, dur, round(rng.uniform(0.01, 1.0), 3), i))
    return out


def test_dp_matches_brute_force_on_random_instances():
    """1200 randomised instances, exact DP vs exhaustive search."""
    rng = random.Random(20260829)
    for trial in range(1200):
        n = rng.randint(0, 11)
        gap = rng.choice([0.0, 1.0, 5.0])
        inst = _random_instance(rng, n)
        dp = optimal_schedule(inst, gap)
        bf = brute_force_optimal(inst, gap)
        assert abs(dp.objective - bf.objective) < 1e-9, (trial, n, gap)
        assert dp.is_feasible(gap)
        assert abs(sum(p.value for p in dp.selected) - dp.objective) < 1e-9


def test_dp_never_worse_than_any_greedy():
    rng = random.Random(7)
    for _ in range(300):
        inst = _random_instance(rng, rng.randint(1, 40))
        gap = rng.choice([0.0, 5.0])
        dp = optimal_schedule(inst, gap)
        for h in (greedy_highest_value, greedy_max_elevation):
            s = h(inst, gap)
            assert s.is_feasible(gap)
            assert dp.objective >= s.objective - 1e-9


def test_dp_beats_greedy_on_a_constructed_trap():
    """Two cheap compatible passes must beat one overlapping expensive pass."""
    a = _mkpass(0, 10, 0.6, 1)
    b = _mkpass(5, 20, 1.0, 2)      # [5, 25): overlaps both a and c
    c = _mkpass(20, 10, 0.6, 3)
    inst = [a, b, c]
    assert abs(optimal_schedule(inst, 0.0).objective - 1.2) < 1e-9
    assert abs(greedy_highest_value(inst, 0.0).objective - 1.0) < 1e-9


def test_setup_gap_is_enforced():
    a = _mkpass(0, 10, 1.0, 1)
    b = _mkpass(12, 10, 1.0, 2)          # only a 2 min gap after a
    s = optimal_schedule([a, b], gap_min=5.0)
    assert s.count == 1
    assert optimal_schedule([a, b], gap_min=1.0).count == 2


def test_empty_and_singleton():
    assert optimal_schedule([], 5.0).count == 0
    assert optimal_schedule([_mkpass(0, 10, 0.5, 1)], 5.0).count == 1
    assert optimal_schedule([_mkpass(0, 10, 0.0, 1)], 5.0).count == 0


def test_identical_intervals_pick_one():
    inst = [_mkpass(0, 10, 0.5, i) for i in range(5)]
    s = optimal_schedule(inst, 0.0)
    assert s.count == 1 and abs(s.objective - 0.5) < 1e-9


def test_genetic_never_exceeds_optimum():
    rng = random.Random(3)
    for _ in range(5):
        inst = _random_instance(rng, 25)
        dp = optimal_schedule(inst, 2.0)
        ga = genetic_schedule(inst, 2.0, population=40, generations=40, seed=1)
        assert ga.is_feasible(2.0)
        assert ga.objective <= dp.objective + 1e-9


def test_capacity_dp_matches_brute_force():
    """Capacity-constrained DP vs exhaustive search on 900 random instances."""
    rng = random.Random(4242)
    for trial in range(900):
        n = rng.randint(0, 10)
        cap = rng.randint(1, 5)
        gap = rng.choice([0.0, 3.0])
        inst = _random_instance(rng, n)
        dp = capacity_schedule(inst, gap, capacity=cap)
        bf = brute_force_capacity(inst, gap, cap)
        assert abs(dp.objective - bf.objective) < 1e-9, (trial, n, cap, gap)
        assert dp.count <= cap
        assert dp.is_feasible(gap)
        assert abs(sum(p.value for p in dp.selected) - dp.objective) < 1e-9


def test_capacity_none_reduces_to_plain_dp():
    rng = random.Random(5)
    for _ in range(50):
        inst = _random_instance(rng, rng.randint(1, 30))
        a = capacity_schedule(inst, 5.0, capacity=None)
        b = optimal_schedule(inst, 5.0)
        assert abs(a.objective - b.objective) < 1e-9


def test_capacity_is_monotone_in_budget():
    rng = random.Random(6)
    inst = _random_instance(rng, 30)
    prev = -1.0
    for cap in range(1, 12):
        v = capacity_schedule(inst, 3.0, capacity=cap).objective
        assert v >= prev - 1e-12
        prev = v
    assert abs(capacity_schedule(inst, 3.0, capacity=99).objective
               - optimal_schedule(inst, 3.0).objective) < 1e-9


def test_capacity_picks_the_most_valuable_when_budget_is_one():
    inst = [_mkpass(0, 5, 0.3, 1), _mkpass(20, 5, 0.9, 2),
            _mkpass(40, 5, 0.5, 3)]
    s = capacity_schedule(inst, 0.0, capacity=1)
    assert s.count == 1 and abs(s.objective - 0.9) < 1e-9


def test_per_night_budget_is_applied_per_night():
    """Two nights, budget 1 each -> exactly one observation on each night."""
    inst = []
    for night in range(2):
        for i in range(4):
            inst.append(_mkpass(night * 1440 + i * 30, 10, 0.2 + 0.1 * i,
                                night * 10 + i))
    s = capacity_schedule(inst, 0.0, capacity=1, per_night=True, lon_deg=0.0)
    nights = {observing_night(p, 0.0) for p in s.selected}
    assert s.count == 2 and len(nights) == 2


def test_observing_night_groups_evening_with_small_hours():
    """22:00 and 02:00 the next morning belong to the same observing night."""
    evening = _mkpass(0, 5, 0.5, 1)
    evening.tca = dt.datetime(2026, 8, 29, 22, 0)
    morning = _mkpass(0, 5, 0.5, 2)
    morning.tca = dt.datetime(2026, 8, 30, 2, 0)
    assert observing_night(evening, 0.0) == observing_night(morning, 0.0)


def _multi_night_instance(rng, n_nights, per_night):
    """Passes spread over several distinct observing nights.

    Culmination elevation is drawn independently of the score, so that an
    elevation-chasing heuristic is genuinely misaligned with the objective --
    which is the situation the scheduler exists to handle. (``_mkpass`` derives
    elevation from the score, which would make the two orderings identical.)
    """
    out, idx = [], 0
    for night in range(n_nights):
        for _ in range(per_night):
            start = night * 1440 + rng.uniform(0, 300)
            p = _mkpass(start, rng.uniform(2, 12),
                        round(rng.uniform(0.05, 1.0), 3), idx)
            p.el_max_deg = rng.uniform(10.0, 90.0)
            out.append(p)
            idx += 1
    return out


def test_budget_dp_matches_brute_force():
    """Two-level (nightly cap + total budget) DP vs exhaustive search."""
    rng = random.Random(99)
    for trial in range(400):
        n_nights = rng.randint(1, 3)
        inst = _multi_night_instance(rng, n_nights, rng.randint(1, 5))
        if len(inst) > 16:
            continue
        cap = rng.randint(1, 3)
        budget = rng.randint(1, 6)
        gap = rng.choice([0.0, 2.0])
        dp = budget_schedule(inst, gap, cap, budget, lon_deg=0.0)
        bf = brute_force_budget(inst, gap, cap, budget, lon_deg=0.0)
        assert abs(dp.objective - bf.objective) < 1e-9, (trial, cap, budget, gap)
        assert dp.count <= budget
        assert dp.is_feasible(gap)
        assert abs(sum(p.value for p in dp.selected) - dp.objective) < 1e-9
        per_night = {}
        for p in dp.selected:
            per_night.setdefault(observing_night(p, 0.0), []).append(p)
        assert all(len(v) <= cap for v in per_night.values())


def test_budget_can_skip_a_night_entirely():
    """Given a budget of 2 over three nights, spend it where the value is."""
    inst = []
    for night, val in enumerate([0.1, 0.9, 0.15]):
        for i in range(3):
            inst.append(_mkpass(night * 1440 + i * 60, 10, val, night * 10 + i))
    s = budget_schedule(inst, 0.0, per_night_cap=1, total_budget=2, lon_deg=0.0)
    assert s.count == 2
    nights = {observing_night(p, 0.0) for p in s.selected}
    assert len(nights) == 2                      # one night is skipped
    assert max(p.value for p in s.selected) == 0.9


def test_budget_reduces_to_capacity_when_budget_is_large():
    rng = random.Random(21)
    inst = _multi_night_instance(rng, 4, 5)
    a = budget_schedule(inst, 2.0, per_night_cap=2, total_budget=10 ** 6,
                        lon_deg=0.0)
    b = capacity_schedule(inst, 2.0, capacity=2, per_night=True, lon_deg=0.0)
    assert abs(a.objective - b.objective) < 1e-9


def test_budget_dp_beats_greedy():
    rng = random.Random(5)
    wins = 0
    for _ in range(60):
        inst = _multi_night_instance(rng, 4, 6)
        dp = budget_schedule(inst, 2.0, 2, 5, lon_deg=0.0)
        gr = greedy_budget(inst, 2.0, 2, 5, key=lambda p: p.el_max_deg,
                           label="g", lon_deg=0.0)
        assert gr.count <= 5 and gr.is_feasible(2.0)
        assert dp.objective >= gr.objective - 1e-9
        if dp.objective > gr.objective + 1e-9:
            wins += 1
    assert wins > 0, "DP should strictly beat the elevation heuristic somewhere"


def test_priority_multiplies_into_value():
    p = _mkpass(0, 10, 0.5, 1)
    p.priority = 2.0
    assert abs(p.value - 1.0) < 1e-12
    assert abs(optimal_schedule([p], 0.0).objective - 1.0) < 1e-12


if __name__ == "__main__":
    fns = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")
        except Exception as e:                       # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
