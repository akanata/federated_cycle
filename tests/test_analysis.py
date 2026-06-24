from datetime import datetime, timedelta

from fit_route_map import Sample
from webapp.analysis import hr_zone, hr_zone_intensity

MAX_HR = 190.0


def test_hr_zone_boundaries():
    assert hr_zone(100, MAX_HR) == 1   # 53% -> Z1
    assert hr_zone(0.65 * MAX_HR, MAX_HR) == 2
    assert hr_zone(0.75 * MAX_HR, MAX_HR) == 3
    assert hr_zone(0.85 * MAX_HR, MAX_HR) == 4
    assert hr_zone(0.95 * MAX_HR, MAX_HR) == 5
    assert hr_zone(None, MAX_HR) == 0


def _series(bpm, n=60):
    t0 = datetime(2026, 1, 1, 12, 0, 0)
    return [Sample(t0 + timedelta(seconds=i), bpm) for i in range(n)]


def test_high_hr_scores_higher_than_low():
    hard = hr_zone_intensity(_series(180), MAX_HR)   # Z5
    easy = hr_zone_intensity(_series(110), MAX_HR)   # Z1
    assert hard > easy
    # 59 one-second intervals; Z5 weight 5, Z1 weight 1.
    assert hard == 59 * 5
    assert easy == 59 * 1


def test_no_hr_is_zero():
    assert hr_zone_intensity([], MAX_HR) == 0.0
    assert hr_zone_intensity(_series(150, n=1), MAX_HR) == 0.0  # single sample, no interval


def test_large_gaps_dont_inflate_score():
    t0 = datetime(2026, 1, 1, 12, 0, 0)
    # Two samples 1 hour apart -> gap clamped to a 1s step, not 3600.
    samples = [Sample(t0, 180), Sample(t0 + timedelta(hours=1), 180)]
    assert hr_zone_intensity(samples, MAX_HR) == 1 * 5
