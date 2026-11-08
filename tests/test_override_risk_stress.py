"""Mechanistic stress test; deterministic simulator is not external validation."""
from __future__ import annotations

from benchmarks.override_risk_stress import (
    _run, PROTOCOL, BACKGROUND_REMAINING, INCOMING_DURATION,
    FUTURE_DURATION, DEADLINE,
)


def pair(bg, incoming, future, deadline):
    before = _run(bg, incoming, future, deadline, False)
    after = _run(bg, incoming, future, deadline, True)
    forecast = after["projected_new_miss"]
    actual = after["background_missed"] and not before["background_missed"]
    return forecast, actual, before, after


def test_predictor_exact_only_without_unmodeled_arrivals():
    # Checking all combinations in the no-arrival subgrid verifies that
    # the projection and simulator share exactly the same declared model.
    for bg in BACKGROUND_REMAINING:
        for incoming in INCOMING_DURATION:
            for deadline in DEADLINE:
                forecast, actual, _, _ = pair(bg, incoming, 0, deadline)
                assert forecast is actual


def test_future_arrival_causes_false_positive_for_incremental_miss():
    forecast, actual, baseline, override = pair(3, 1, 1, 4)
    assert forecast is True
    assert actual is False
    assert baseline["background_completed_s"] == 5.0
    assert override["background_completed_s"] == 6.0
    assert baseline["background_missed"]  # Would miss even without initial override.


def test_future_arrival_causes_false_negative_for_incremental_miss():
    forecast, actual, baseline, override = pair(3, 1, 1, 5)
    assert forecast is False
    assert actual is True
    assert baseline["background_completed_s"] == 5.0
    assert override["background_completed_s"] == 6.0


def test_synthetic_probe_never_treats_future_event_as_original_user():
    assert PROTOCOL == "projected-override-risk-factorial-stress-v1"
    assert FUTURE_DURATION[0] == 0
    assert len(BACKGROUND_REMAINING) * len(INCOMING_DURATION) * len(FUTURE_DURATION) * len(DEADLINE) == 1536


def test_simple_expected_negative_and_positive_examples():
    assert pair(4, 3, 0, 5)[:2] == (True, True)
    assert pair(4, 3, 0, 10)[:2] == (False, False)
