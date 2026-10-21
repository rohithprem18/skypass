"""Tests for the shipped planner configuration: forecast calibration and the
nightly-capacity / window-budget schedulers, through the library, the CLI and
the web API. Run with:  python -m pytest tests -q

Every weather product is replaced by a synthetic series, and the HTTP layer is
made to fail loudly, so these tests never touch the network.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import skypass.pipeline as pipeline
import skypass.weather as weather
from skypass import cli
from skypass.config import GROUND_STATIONS
from skypass.pipeline import plan
from skypass.scheduler import observing_night
from skypass.scoring import MODE_RADIO
from skypass.timeutil import hour_key
from skypass.tle import parse_tle_text
from skypass.weather import CloudCalibration, CloudSeries, WeatherUnavailable

ISS_L1 = "1 25544U 98067A   24274.52916667  .00016717  00000-0  30074-3 0  9990"
ISS_L2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49814641    46"
RECORDS = parse_tle_text(f"ISS (ZARYA)\n{ISS_L1}\n{ISS_L2}\n")

#: Near the fixture epoch. Leh sees optical ISS passes in this window, and
#: Chennai sees enough radio passes over several nights to exercise budgets.
T0 = dt.datetime(2024, 9, 30, 12, 0, 0)
DAYS = 4.0
OPTICAL_SITE = GROUND_STATIONS["leh"]
RADIO_SITE = GROUND_STATIONS["chennai"]


def constant_clouds(value: float, t0: dt.datetime = T0, days: int = 6):
    return CloudSeries({hour_key(t0 + dt.timedelta(hours=h)): value
                        for h in range(-24, 24 * days)}, label="forecast")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any attempt to reach Open-Meteo is a test failure, not a slow retry."""
    def refuse(url, *a, **k):
        raise AssertionError(f"network access attempted: {url}")
    monkeypatch.setattr(weather, "_fetch_json", refuse)


# ---------------------------------------------------------------------------
# weather.site_calibration
# ---------------------------------------------------------------------------
def _hourly(start: dt.date, end: dt.date):
    t = dt.datetime.combine(start, dt.time())
    stop = dt.datetime.combine(end, dt.time()) + dt.timedelta(days=1)
    while t < stop:
        yield t
        t += dt.timedelta(hours=1)


def _mock_training_data(monkeypatch, night_rel, day_rel, calls):
    """Forecast varies smoothly; truth follows ``night_rel`` at local night
    and ``day_rel`` by day, so a fit that leaks daytime hours is detectable."""
    is_night = weather.night_hours_filter(OPTICAL_SITE.lon_deg)

    def fake_previous_runs(site, start, end, lead_days=(1,), cache_dir=None):
        calls["previous_runs"] = (start, end, tuple(lead_days))
        vals = {hour_key(t): ((t.hour * 7 + t.day * 3) % 20) / 20.0
                for t in _hourly(start, end)}
        return {k: CloudSeries(dict(vals), f"lead-{k}d") for k in lead_days}

    def fake_reanalysis(site, start, end, cache_dir=None, model="era5"):
        calls["reanalysis"] = (start, end, model)
        fc = fake_previous_runs(site, start, end)[1].values
        return CloudSeries({k: (night_rel if is_night(k) else day_rel)(v)
                            for k, v in fc.items()}, model)

    monkeypatch.setattr(weather, "previous_runs", fake_previous_runs)
    monkeypatch.setattr(weather, "reanalysis", fake_reanalysis)


def test_site_calibration_fits_night_hours_before_the_plan(monkeypatch):
    calls = {}
    _mock_training_data(monkeypatch, night_rel=lambda f: 0.3 + 0.5 * f,
                        day_rel=lambda f: 1.0 - f, calls=calls)
    before = dt.date(2024, 9, 30)
    cal = weather.site_calibration(OPTICAL_SITE, before, train_days=90,
                                   lead_days=1)
    # Window: the 90 days ending the day before the plan, ERA5 pinned.
    assert calls["previous_runs"] == (dt.date(2024, 7, 2),
                                      dt.date(2024, 9, 29), (1,))
    assert calls["reanalysis"] == (dt.date(2024, 7, 2),
                                   dt.date(2024, 9, 29), "era5")
    # Recovers the night relation exactly; the opposite daytime relation
    # would pull the slope negative if it leaked into the fit.
    assert abs(cal.intercept - 0.3) < 1e-9
    assert abs(cal.slope - 0.5) < 1e-9
    assert abs(cal.correlation - 1.0) < 1e-9
    assert cal.n >= weather.MIN_CALIBRATION_HOURS
    assert cal.n < 90 * 24                     # daytime hours excluded


def test_site_calibration_short_record_is_identity(monkeypatch):
    calls = {}
    _mock_training_data(monkeypatch, night_rel=lambda f: 0.9,
                        day_rel=lambda f: 0.9, calls=calls)
    cal = weather.site_calibration(OPTICAL_SITE, dt.date(2024, 9, 30),
                                   train_days=1)
    assert cal.n < weather.MIN_CALIBRATION_HOURS
    assert (cal.intercept, cal.slope) == (0.0, 1.0)


# ---------------------------------------------------------------------------
# pipeline.plan: calibration
# ---------------------------------------------------------------------------
def _scores(result):
    return {p.key(): p for p in result.passes}


def test_plan_scores_the_calibrated_forecast():
    raw = constant_clouds(0.2)
    cal = CloudCalibration(intercept=0.6, slope=0.0, n=500, correlation=0.4)
    blind_cal = plan(site=OPTICAL_SITE, days=DAYS, t0=T0, records=RECORDS,
                     clouds=raw, fetch_weather=False, calibrate=False)
    calib = plan(site=OPTICAL_SITE, days=DAYS, t0=T0, records=RECORDS,
                 clouds=raw, fetch_weather=False, calibration=cal)
    assert blind_cal.calibration is None
    assert calib.calibration is cal
    assert calib.summary()["calibrated"] is True
    assert calib.summary()["calibration"]["intercept"] == 0.6

    a, b = _scores(blind_cal), _scores(calib)
    assert a.keys() == b.keys()
    scored = [k for k, p in b.items() if p.detail.get("cloud") is not None
              and a[k].score > 0]
    assert scored, "fixture must yield at least one scored optical pass"
    for k in scored:
        assert abs(b[k].detail["cloud"] - 0.6) < 1e-12
        assert abs(b[k].detail["cloud_raw"] - 0.2) < 1e-12
        # f_sky goes from (1 - 0.2) to (1 - 0.6): exactly half the score.
        assert abs(b[k].score - 0.5 * a[k].score) < 1e-12


def test_plan_fits_calibration_by_default(monkeypatch):
    seen = {}

    def fake_site_calibration(site, before, train_days, lead_days):
        seen.update(site=site, before=before, train_days=train_days,
                    lead_days=lead_days)
        return CloudCalibration(0.1, 0.5, 300, 0.6)

    monkeypatch.setattr(pipeline, "site_calibration", fake_site_calibration)
    r = plan(site=OPTICAL_SITE, days=DAYS, t0=T0, records=RECORDS,
             clouds=constant_clouds(0.4), fetch_weather=False)
    assert seen == {"site": OPTICAL_SITE, "before": T0.date(),
                    "train_days": 90, "lead_days": 1}
    assert r.calibration is not None and r.calibration.slope == 0.5
    for p in r.passes:
        if p.detail.get("cloud") is not None:
            assert abs(p.detail["cloud"] - 0.3) < 1e-12


def test_plan_falls_back_to_raw_forecast_without_calibration_data(monkeypatch):
    def unavailable(*a, **k):
        raise WeatherUnavailable("offline")

    monkeypatch.setattr(pipeline, "site_calibration", unavailable)
    r = plan(site=OPTICAL_SITE, days=DAYS, t0=T0, records=RECORDS,
             clouds=constant_clouds(0.4), fetch_weather=False)
    assert r.calibration is None and r.weather_used
    for p in r.passes:
        if p.detail.get("cloud") is not None:
            assert abs(p.detail["cloud"] - 0.4) < 1e-12
            assert "cloud_raw" not in p.detail


def test_plan_ignores_a_fit_on_too_few_hours():
    cal = CloudCalibration(0.0, 1.0, 5, float("nan"))
    r = plan(site=OPTICAL_SITE, days=DAYS, t0=T0, records=RECORDS,
             clouds=constant_clouds(0.4), fetch_weather=False, calibration=cal)
    assert r.calibration is None


def test_weather_blind_plan_never_calibrates(monkeypatch):
    def must_not_run(*a, **k):
        raise AssertionError("calibration fitted for a weather-blind plan")

    monkeypatch.setattr(pipeline, "site_calibration", must_not_run)
    r = plan(site=RADIO_SITE, days=DAYS, t0=T0, records=RECORDS,
             mode=MODE_RADIO, weather_aware=False, fetch_weather=False)
    assert r.calibration is None


# ---------------------------------------------------------------------------
# pipeline.plan: capacity and budget routing
# ---------------------------------------------------------------------------
def _radio(**kw):
    return plan(site=RADIO_SITE, days=DAYS, t0=T0, records=RECORDS,
                mode=MODE_RADIO, weather_aware=False, fetch_weather=False,
                **kw)


def _per_night(result):
    counts = {}
    for p in result.schedule.selected:
        n = observing_night(p, RADIO_SITE.lon_deg)
        counts[n] = counts.get(n, 0) + 1
    return counts


def test_unconstrained_plan_uses_the_plain_dp():
    r = _radio()
    assert r.schedule.algorithm == "dp-optimal"
    assert r.capacity is None and r.budget is None
    assert max(_per_night(r).values()) > 1, \
        "fixture must have nights with more than one pass"


def test_capacity_routes_to_per_night_dp():
    r = _radio(capacity=1)
    assert r.schedule.algorithm == "dp-capacity-1-per-night"
    assert max(_per_night(r).values()) == 1
    assert len(_per_night(r)) == len(_per_night(_radio()))
    assert r.summary()["capacity_per_night"] == 1
    assert r.summary()["window_budget"] is None


def test_budget_routes_to_budget_dp_and_skips_nights():
    unconstrained = _per_night(_radio())
    r = _radio(capacity=2, budget=3)
    assert r.schedule.algorithm == "dp-budget-2x3"
    assert r.schedule.count == 3
    assert max(_per_night(r).values()) <= 2
    assert len(_per_night(r)) < len(unconstrained)       # some nights skipped
    assert r.summary()["window_budget"] == 3


def test_budget_without_capacity_uses_the_configured_nightly_cap():
    r = _radio(budget=4)
    assert r.capacity == 3
    assert r.schedule.algorithm == "dp-budget-3x4"
    assert r.schedule.count <= 4


def test_non_positive_limits_are_rejected():
    with pytest.raises(ValueError):
        _radio(capacity=0)
    with pytest.raises(ValueError):
        _radio(budget=0)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
class _Stop(Exception):
    pass


def test_cli_passes_calibration_capacity_and_budget(monkeypatch):
    got = {}

    def fake_plan(**kw):
        got.update(kw)
        raise _Stop

    monkeypatch.setattr(cli, "plan", fake_plan)
    with pytest.raises(_Stop):
        cli.main(["plan", "--capacity", "2", "--budget", "5"])
    assert got["calibrate"] is True
    assert (got["capacity"], got["budget"]) == (2, 5)

    got.clear()
    with pytest.raises(_Stop):
        cli.main(["plan", "--no-calibrate"])
    assert got["calibrate"] is False
    assert got["capacity"] is None and got["budget"] is None


def test_cli_rejects_non_positive_budget():
    for bad in (["plan", "--budget", "0"], ["plan", "--capacity", "-1"],
                ["plan", "--budget", "two"]):
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args(bad)


# ---------------------------------------------------------------------------
# Web API
# ---------------------------------------------------------------------------
@pytest.fixture
def web(monkeypatch):
    from webapp import server
    server._CALIBRATIONS.clear()
    monkeypatch.setattr(server, "records", lambda: RECORDS)
    monkeypatch.setattr(server, "utcnow", lambda: T0)
    monkeypatch.setattr(server, "forecast",
                        lambda site, days=16: constant_clouds(0.2))
    fits = []

    def fake_site_calibration(site, day, train_days, lead_days):
        fits.append((site.name, day))
        return CloudCalibration(0.6, 0.0, 500, 0.4)

    monkeypatch.setattr(server, "site_calibration", fake_site_calibration)
    server._test_fits = fits
    yield server
    server._CALIBRATIONS.clear()


def test_api_plan_is_calibrated_and_budgeted(web):
    out = web.build_plan({"station": "leh", "days": "4", "capacity": "1",
                          "budget": "2"})
    assert out["weather_used"] and out["calibrated"]
    assert out["calibration"]["intercept"] == 0.6
    assert out["capacity"] == 1 and out["budget"] == 2
    assert out["algorithm"] == "dp-budget-1x2"
    assert len(out["passes"]) <= 2
    for p in out["candidates"]:
        if p["cloud"] is not None:
            assert abs(p["cloud"] - 0.6) < 1e-12
            assert abs(p["cloud_raw"] - 0.2) < 1e-12
    # A second request on the same day reuses the fit.
    web.build_plan({"station": "leh", "days": "4"})
    assert web._test_fits == [(OPTICAL_SITE.name, T0.date())]


def test_api_plan_can_opt_out_of_calibration(web):
    out = web.build_plan({"station": "leh", "days": "4", "calibrate": "0"})
    assert out["calibrated"] is False and out["calibration"] is None
    assert web._test_fits == []
    for p in out["candidates"]:
        if p["cloud"] is not None:
            assert abs(p["cloud"] - 0.2) < 1e-12


def test_api_plan_capacity_only_keeps_the_nightly_quota(web):
    out = web.build_plan({"station": "chennai", "days": "4", "mode": "radio",
                          "weather": "0", "capacity": "1"})
    assert out["algorithm"] == "dp-capacity-1-per-night"
    assert out["budget"] == 0 and out["calibrated"] is False
    nights = [p["night"] for p in out["passes"]]
    assert len(nights) == len(set(nights))
