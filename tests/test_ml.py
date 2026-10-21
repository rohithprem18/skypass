"""Tests for the optional learned components and the nowcast hook.

The ML tests skip cleanly when the optional [ml] dependencies are absent, so
the core suite still runs with sgp4 alone. None of them needs the network or
the downloaded datasets.
"""
import datetime as dt
import math

import pytest

np = pytest.importorskip("numpy")


# ---------------------------------------------------------------------------
# brightness
# ---------------------------------------------------------------------------
def test_satellite_family_recognises_constellations_and_classes():
    from skypass.ml.brightness import satellite_family
    assert satellite_family("STARLINK-31234") == "STARLINK"
    assert satellite_family("KUIPER-00033") == "KUIPER"
    assert satellite_family("SL-16 R/B") == "ROCKET BODY"
    assert satellite_family("COSMOS 2251 DEB") == "DEBRIS"
    assert satellite_family("ISS (ZARYA)") == "OTHER"


def test_observing_band_mapping():
    from skypass.ml.brightness import observing_band
    assert observing_band("VISUAL", "CLEAR") == "VISUAL"
    assert observing_band("CCD", "r") == "r"
    assert observing_band("CMOS", "Gaia G") == "G"
    assert observing_band("CMOS", "CLEAR") == "CLEAR"
    assert observing_band("CCD", "Ha") == "OTHER"


def test_sphere_magnitude_matches_planner_photometry():
    from skypass.geometry import apparent_magnitude
    from skypass.ml.brightness import sphere_magnitude
    assert sphere_magnitude(5.0, 1000.0, 0.0) == pytest.approx(5.0)
    assert sphere_magnitude(4.0, 2000.0, 60.0) == pytest.approx(
        apparent_magnitude(4.0, 2000.0, math.radians(60.0)))


def test_regression_metrics_visibility_decision():
    from skypass.ml.brightness import regression_metrics
    m = regression_metrics([5.0, 7.0, 4.0, 8.0], [5.5, 6.5, 6.5, 8.0], limit=6.0)
    assert m["mae"] == pytest.approx(0.875)
    # predictions say visible, not visible, not visible, not visible
    assert m["visibility_accuracy"] == pytest.approx(0.75)
    assert m["visibility_balanced_accuracy"] == pytest.approx(0.75)


def test_fitted_sphere_learns_family_offsets():
    pd = pytest.importorskip("pandas")
    from skypass.ml.brightness import SphereBaseline, sphere_magnitude
    rows = []
    for fam, std in (("STARLINK", 4.0), ("KUIPER", 6.0)):
        for r, ph in ((800, 30), (1200, 60), (1500, 90)):
            rows.append({"name": f"{fam}-1", "family": fam, "range_km": r,
                         "phase_deg": ph, "mag": sphere_magnitude(std, r, ph)})
    df = pd.DataFrame(rows)
    base = SphereBaseline(fitted=True).fit(df)
    assert base.family_std["STARLINK"] == pytest.approx(4.0)
    assert np.allclose(base.predict(df), df["mag"])


# ---------------------------------------------------------------------------
# cloud camera
# ---------------------------------------------------------------------------
def test_blocked_folds_are_contiguous_and_cover_everything():
    from skypass.ml.cloudcam import blocked_folds
    folds = blocked_folds(10, 5)
    seen = []
    for tr, te in folds:
        assert te == list(range(te[0], te[-1] + 1))
        assert not set(tr) & set(te)
        seen += te
    assert sorted(seen) == list(range(10))


def test_ratio_threshold_and_metrics_on_synthetic_sky():
    from skypass.ml.cloudcam import IGNORE, RatioThreshold, segmentation_metrics
    img = np.zeros((4, 4, 3), np.uint8)
    img[:, :2] = (60, 90, 200)      # blue sky: R/B = 0.3
    img[:, 2:] = (200, 200, 205)    # white cloud: R/B ~ 1
    lab = np.zeros((4, 4), np.int8)
    lab[:, 2:] = 1
    lab[0, 0] = IGNORE
    pred = RatioThreshold(0.6).predict(img)
    m = segmentation_metrics([pred], [lab])
    assert m["pixel_accuracy"] == 1.0 and m["cloud_iou"] == 1.0
    assert m["fraction_mae"] == pytest.approx(0.0)


def test_pixel_gbm_learns_and_round_trips(tmp_path):
    pytest.importorskip("sklearn")
    from skypass.ml.cloudcam import PixelGBM, cloud_fraction
    img = np.zeros((24, 24, 3), np.uint8)
    img[:, :12] = (60, 90, 200)
    img[:, 12:] = (200, 200, 205)
    lab = np.zeros((24, 24), np.int8)
    lab[:, 12:] = 1
    m = PixelGBM(pixels_per_image=400).fit(np.stack([img, img]), np.stack([lab, lab]))
    assert (m.predict(img) == lab).mean() > 0.95
    path = m.save(str(tmp_path / "gbm.pkl"))
    loaded = PixelGBM.load(path)
    assert (loaded.predict(img) == m.predict(img)).all()
    assert cloud_fraction(img, model=loaded) == pytest.approx(0.5, abs=0.05)


def test_tuned_threshold_separates_classes():
    from skypass.ml.cloudcam import RatioThreshold
    img = np.zeros((2, 8, 3), np.uint8)
    img[:, :4] = (100, 120, 200)    # R/B = 0.5
    img[:, 4:] = (190, 190, 200)    # R/B = 0.95
    lab = np.zeros((2, 8), np.int8)
    lab[:, 4:] = 1
    t = RatioThreshold(None).fit(img[None], lab[None])
    assert np.array_equal(t.predict(img), lab)


def test_pixel_features_shape():
    from skypass.ml.cloudcam import pixel_features
    f = pixel_features(np.random.default_rng(0).integers(0, 255, (12, 10, 3), np.uint8))
    assert f.shape == (120, 15) and np.isfinite(f).all()


# ---------------------------------------------------------------------------
# nowcast hook in the planner (no ML dependencies needed)
# ---------------------------------------------------------------------------
def test_plan_rejects_invalid_nowcast():
    from skypass import plan
    from skypass.weather import CloudSeries
    with pytest.raises(ValueError):
        plan(days=0.1, clouds=CloudSeries({}), fetch_weather=False,
             calibrate=False, nowcast=1.5, limit=1)


def test_plan_nowcast_overrides_the_next_hour():
    from skypass import plan
    from skypass.timeutil import hour_key
    from skypass.weather import CloudSeries
    t0 = dt.datetime(2026, 8, 29, 12, 0)
    forecast = CloudSeries({hour_key(t0 + dt.timedelta(hours=h)): 0.9 for h in range(30)})
    res = plan(t0=t0, days=1.0, clouds=forecast, fetch_weather=False,
               calibrate=False, nowcast=0.1, nowcast_hours=1.0, limit=40)
    for p in res.passes:
        c = p.detail.get("cloud")
        if c is None:
            continue
        hours = (p.tca - t0).total_seconds() / 3600.0
        if hours <= 1.0:
            assert c == pytest.approx(0.1)
        elif hours >= 3.0:
            assert c == pytest.approx(0.9)
