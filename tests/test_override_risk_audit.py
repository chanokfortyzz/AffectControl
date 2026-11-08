"""Risk projection checks: no silent suppression of explicit user decisions."""
from __future__ import annotations

import math

import pytest

from affectcontrol import (
    AffectiveScheduler, ControlBias, TaskRecord, TaskSpec,
    reference_policy,
)
from affectcontrol.override_risk import projected_override_risk
from test_explicit_override_priority import control_for


def records(*, deadline=5.0, duration=4.0, incoming_duration=3.0,
            provenance="synthetic"):
    background = TaskRecord(TaskSpec(
        "background", "sensitive user message is not for public metrics",
        duration, "P0", deadline_s=deadline,
        metadata={"deadline_basis": provenance},
    ))
    incoming = TaskRecord(TaskSpec(
        "incoming", "urgent user content is private",
        incoming_duration, "P3", deadline_s=20,
    ))
    return background, incoming


def test_incremental_deadline_miss_is_quantified_but_not_policy():
    old, new = records()
    r = projected_override_risk(1.0, old, new)
    assert r.status == "newly_projected_miss"
    assert r.projected_finish_no_override_s == 5.0
    assert r.projected_finish_with_override_s == 8.0
    assert r.additional_delay_s == 3
    assert r.newly_projected_deadline_miss is True
    assert r.deadline_basis == "synthetic"
    assert r.predictive_scope == "conditional_on_no_future_arrivals"
    assert r.external_calibration_status == "unvalidated"
    assert "sensitive user message" not in str(r.asdict())


def test_known_safe_and_preexisting_miss_are_distinct():
    a,b=records(deadline=9)
    assert projected_override_risk(1,a,b).status == "no_new_projected_miss"
    a,b=records(deadline=4)
    r=projected_override_risk(1,a,b)
    assert r.status == "already_projected_miss"
    assert r.newly_projected_deadline_miss is False


def test_missing_deadline_is_unknown_not_safe():
    a,b=records(deadline=None)
    r=projected_override_risk(1,a,b)
    assert r.status == "no_deadline"
    assert r.newly_projected_deadline_miss is None
    assert r.projected_finish_no_override_s is None


@pytest.mark.parametrize("field,value", [
    ("deadline",float("nan")),
    ("deadline",float("inf")),
    ("duration",float("nan")),
    ("duration",-1),
    ("incoming_duration",float("inf")),
])
def test_nonfinite_or_negative_inputs_cannot_be_reported_safe(field,value):
    kw={field:value}
    a,b=records(**kw)
    r=projected_override_risk(1,a,b)
    assert r.status == "unquantifiable"
    assert r.newly_projected_deadline_miss is None


def test_unverified_deadline_provenance_remains_unverified():
    a,b=records(provenance="owner_verified")
    assert projected_override_risk(1,a,b).deadline_basis == "unspecified"


def scheduler_scenario(*, deadline=5.0, preemptible=True,
                       explicit=True, strategy="affective"):
    policy=reference_policy(warn=False)
    s=AffectiveScheduler(policy.scheduler,strategy=strategy)
    s.add_task(TaskSpec(
        "background", "background", 4, "P0",
        deadline_s=deadline, preemptible=preemptible,
        metadata={"deadline_basis":"synthetic"},
    ), ControlBias(effective_priority="P0",should_interrupt=False))
    s.step(1)
    s.add_task(TaskSpec(
        "incoming", "routine text", 3, "P3", deadline_s=20,
        metadata={"explicit_override":explicit,"urgency_score":0.3},
    ),control_for("routine text",explicit=explicit))
    return s


def test_live_override_records_projection_but_still_runs_user_request():
    s=scheduler_scenario()
    s.step(1)
    assert s.current_id == "incoming"
    assert s.metrics.override_displaced_task_projections == 1
    assert s.metrics.override_newly_projected_misses == 1
    assert len(s.override_risk_events) == 1
    event=s.override_risk_events[0]
    assert event["projected_finish_no_override_s"] == 4
    assert event["projected_finish_with_override_s"] == 7
    assert event["deadline_basis"] == "synthetic"
    assert "routine text" not in str(event)
    s.run_until_idle()
    summary=s.metrics.summary()
    assert summary["deadline_miss_rate"] == 0.5
    assert summary["override_newly_projected_misses"] == 1
    assert s.metrics.deadline_misses == 1


def test_risk_missing_deadline_is_counted_as_unknown_not_safe():
    s=scheduler_scenario(deadline=None)
    s.step(1)
    assert s.current_id == "incoming"
    assert s.metrics.override_missing_deadline_projections == 1
    assert s.metrics.override_newly_projected_misses == 0
    assert s.override_risk_events[0]["newly_projected_deadline_miss"] is None


def test_nonpreemptible_task_has_no_override_preemption_risk_record():
    s=scheduler_scenario(preemptible=False)
    s.step(1)
    assert s.current_id == "background"
    assert s.metrics.override_displaced_task_projections == 0
    assert not s.override_risk_events


def test_no_spurious_risk_for_ordinary_lexical_urgency():
    s=scheduler_scenario(explicit=False)
    s.step(1)
    assert s.current_id == "background"
    assert not s.override_risk_events


def test_comparator_not_changed_and_no_extra_audit_side_effects():
    s=scheduler_scenario(strategy="static")
    s.step(1)
    assert s.current_id == "background"
    assert s.metrics.override_displaced_task_projections == 0


def test_exactly_at_deadline_is_not_projected_as_miss():
    a,b=records(deadline=8)
    r=projected_override_risk(1,a,b)
    assert r.projected_finish_with_override_s == 8
    assert r.status == "no_new_projected_miss"
