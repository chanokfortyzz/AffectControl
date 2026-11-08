"""Behavioral guard for explicit user hard overrides; not a performance claim."""
from __future__ import annotations

import pytest

from affectcontrol import (
    AffectControlHarness, AffectiveScheduler, ControlBias, ControlPolicy,
    Event, KeywordRuleBaseline, MemoryControl, StateEngine, TaskSpec,
    TaskStatus, reference_policy,
)


def control_for(text, base_priority="P3", explicit=False):
    policy = reference_policy(warn=False)
    h = AffectControlHarness(KeywordRuleBaseline(policy.rule),
                             state_engine=StateEngine(policy.state),
                             control=ControlPolicy(policy.control),
                             memory=MemoryControl(policy.memory))
    return h.process(Event(text, task_id="incoming", explicit_user_immediate=explicit),
                     base_priority=base_priority)["control"]


def extreme_background(*, preemptible=True, strategy="affective"):
    policy = reference_policy(warn=False)
    s = AffectiveScheduler(policy.scheduler, strategy=strategy)
    s.add_task(
        TaskSpec("background", "routine background", 30, base_priority="P0",
                 deadline_s=2, preemptible=preemptible),
        ControlBias(effective_priority="P0", should_interrupt=False),
    )
    s.step()
    assert s.current_id == "background"
    return s


def add_incoming(s, *, base_priority="P3", text="routine work", explicit=False,
                 metadata_override=None):
    control = control_for(text, base_priority, explicit)
    if metadata_override is None:
        metadata_override = explicit
    spec = TaskSpec("incoming", text, 5, base_priority=base_priority,
                    deadline_s=200, preemptible=True,
                    metadata={"explicit_override": metadata_override,
                              "expected_interrupt": explicit, "urgency_score": 1.0 if "urgent" in text else 0.3})
    s.add_task(spec, control)
    return control


@pytest.mark.parametrize("base_priority", ("P0", "P1", "P2", "P3"))
@pytest.mark.parametrize("text", ("routine work", "urgent do this right now"))
def test_explicit_override_preempts_very_high_scored_preemptible_background(base_priority, text):
    s = extreme_background()
    bias = add_incoming(s, base_priority=base_priority, text=text, explicit=True)
    assert "explicit_user_immediate_hard_override" in bias.reasons
    s.step()
    assert s.current_id == "incoming"
    assert s.tasks["background"].status == TaskStatus.PAUSED
    assert s.metrics.preemptions == 1
    assert s.metrics.summary()["user_override_compliance"] == 1.0


def test_nonpreemptible_background_remains_protected():
    s = extreme_background(preemptible=False)
    add_incoming(s, explicit=True)
    s.step()
    assert s.current_id == "background"
    assert s.tasks["incoming"].status == TaskStatus.QUEUED
    assert s.metrics.preemptions == 0


def test_explicit_override_prioritized_among_already_queued_tasks():
    policy = reference_policy(warn=False)
    s = AffectiveScheduler(policy.scheduler)
    s.add_task(TaskSpec("rival", "rival", 5, base_priority="P0", deadline_s=2),
               ControlBias(effective_priority="P0", should_interrupt=True))
    add_incoming(s, explicit=True)
    s.step()
    assert s.current_id == "incoming"


def test_active_explicit_override_not_displaced_by_other_ordinary_task():
    policy = reference_policy(warn=False)
    s = AffectiveScheduler(policy.scheduler)
    add_incoming(s, explicit=True)
    s.step()
    assert s.current_id == "incoming"
    s.add_task(TaskSpec("rival", "rival", 1, base_priority="P0", deadline_s=1),
               ControlBias(effective_priority="P0", should_interrupt=True))
    s.step()
    assert s.current_id == "incoming"


def test_spoofed_metadata_without_real_control_override_is_not_hard_override():
    s = extreme_background()
    add_incoming(s, explicit=False, metadata_override=True)
    s.step()
    assert s.current_id == "background"


def test_static_comparator_not_modified_by_affective_override_fix():
    s = extreme_background(strategy="static")
    add_incoming(s, explicit=True)
    s.step()
    assert s.current_id == "background"


def test_end_to_end_trace_user_immediate_flag_reaches_scheduler():
    from affectcontrol import TraceEvent, TraceRunner, WorkflowTrace
    policy = reference_policy(warn=False)
    harness = AffectControlHarness(
        KeywordRuleBaseline(policy.rule), state_engine=StateEngine(policy.state),
        control=ControlPolicy(policy.control), memory=MemoryControl(policy.memory),
    )
    trace = WorkflowTrace(
        "hard-override-end-to-end",
        [
            TraceEvent(0, "arrive", "background",
                       {"text": "routine report", "duration_s": 30,
                        "priority": "P0", "deadline_s": 2, "preemptible": True}),
            TraceEvent(2, "arrive", "incoming",
                       {"text": "routine work", "duration_s": 5,
                        "priority": "P3", "deadline_s": 100, "immediate": True}),
        ],
        max_runtime_s=60,
    )
    result = TraceRunner(harness, AffectiveScheduler(policy.scheduler)).run(trace)
    assert result["preemptions"] >= 1
    assert result["user_override_compliance"] == 1.0


def test_urgent_text_is_not_a_user_confirmed_immediate_flag():
    s = extreme_background()
    control = add_incoming(s, base_priority="P3",
                           text="urgent do this right now", explicit=False)
    assert "explicit_user_immediate_hard_override" not in control.reasons
    s.step()
    assert s.current_id == "background"


def test_other_strategies_continue_to_use_their_own_rankings():
    # Fair experimental controls must not silently inherit the Affective
    # strategy's explicit-user hard-override policy.
    for strategy in ("static", "edf"):
        s = extreme_background(strategy=strategy)
        add_incoming(s, explicit=True)
        s.step()
        assert s.current_id == "background"


def test_multiple_explicit_commands_follow_queue_order():
    policy = reference_policy(warn=False)
    s = AffectiveScheduler(policy.scheduler)
    s.add_task(TaskSpec("first", "first", 6, base_priority="P3",
                        metadata={"explicit_override": True}),
               control_for("routine work", explicit=True))
    s.add_task(TaskSpec("second", "second", 6, base_priority="P3",
                        metadata={"explicit_override": True}),
               control_for("routine work", explicit=True))
    s.step()
    assert s.current_id == "first"
    s.run_until_idle()
    assert s.tasks["first"].completed_at_s < s.tasks["second"].completed_at_s
