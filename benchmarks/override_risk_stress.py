"""Reproducible factorial simulator stress test of displacement-risk projections.

This study tests an intentionally limited two-task forecast against matched
deterministic scheduler outcomes. External arrivals represent a documented
model violation, not actual user/Agent data. Never use as E2 evidence.
"""
from __future__ import annotations

from collections import Counter
from itertools import product
import hashlib
import json

from affectcontrol import (
    AffectiveScheduler, ControlBias, TaskSpec, TaskStatus, reference_policy,
)

PROTOCOL = "projected-override-risk-factorial-stress-v1"
BACKGROUND_REMAINING = (3, 4, 5, 6)
INCOMING_DURATION = (1, 2, 3, 4)
FUTURE_DURATION = (0, 1, 2, 3, 4, 5)
DEADLINE = tuple(range(3, 19))


def _control(explicit):
    if explicit:
        return ControlBias(
            effective_priority="P0", should_interrupt=True, drive=1.0,
            interrupt_score=1.0,
            reasons=["explicit_user_immediate_hard_override"],
        )
    return ControlBias(effective_priority="P3", should_interrupt=False)


def _run(background_remaining, incoming_duration, future_duration, deadline, explicit):
    policy = reference_policy(warn=False)
    s = AffectiveScheduler(policy.scheduler, strategy="affective")
    s.add_task(
        TaskSpec(
            "background", "synthetic background", background_remaining + 1,
            base_priority="P0", deadline_s=deadline, preemptible=True,
            metadata={"deadline_basis": "synthetic"},
        ),
        ControlBias(effective_priority="P0", should_interrupt=False),
    )
    s.step(1)  # now=1, after one actual simulated second of background work
    s.add_task(
        TaskSpec(
            "incoming", "synthetic user message", incoming_duration,
            base_priority="P3", deadline_s=100,
            metadata={"explicit_override": explicit},
        ),
        _control(explicit),
    )
    s.step(1)  # at t=1 an explicit request can preempt background
    projected = s.override_risk_events[0]["newly_projected_deadline_miss"] if explicit else None
    if future_duration:
        # Exogenous competing immediate command at t=2 in BOTH arms.
        # This violates the original projection's no-future-arrivals assumption.
        s.add_task(
            TaskSpec(
                "future", "independent synthetic immediate arrival",
                future_duration, base_priority="P3",
                deadline_s=100,
                metadata={"explicit_override": True},
            ),
            _control(True),
        )
    s.run_until_idle(max_s=120)
    rec = s.tasks["background"]
    if rec.status != TaskStatus.DONE:
        raise AssertionError("stress scenario did not finish")
    return {
        "background_missed": rec.completed_at_s > deadline,
        "background_completed_s": rec.completed_at_s,
        "incoming_completed_s": s.tasks["incoming"].completed_at_s,
        "projected_new_miss": projected,
        "new_projected_counter": s.metrics.override_newly_projected_misses,
    }


def analyze():
    cases = list(product(
        BACKGROUND_REMAINING, INCOMING_DURATION, FUTURE_DURATION, DEADLINE,
    ))
    plan = {
        "protocol": PROTOCOL,
        "background_remaining": BACKGROUND_REMAINING,
        "incoming_duration": INCOMING_DURATION,
        "future_duration": FUTURE_DURATION,
        "deadlines": DEADLINE,
        "n_scenarios": len(cases),
        "future_event_at_s": 2,
        "source": "authored deterministic research simulator only",
    }
    groups = {
        "no_future_arrival": Counter(),
        "future_explicit_arrival_at_2s": Counter(),
    }
    examples = {"false_positive": None, "false_negative": None}
    for background, incoming, future, deadline in cases:
        base = _run(background, incoming, future, deadline, False)
        treated = _run(background, incoming, future, deadline, True)
        predicted = treated["projected_new_miss"]
        if type(predicted) is not bool:
            raise AssertionError("unexpected missing projection in fully specified case")
        # Potential *incremental* loss vs identical external-event baseline,
        # rather than the marginal treated-arm failure status.
        realized = treated["background_missed"] and not base["background_missed"]
        group = groups["future_explicit_arrival_at_2s" if future else "no_future_arrival"]
        cell = ("TP" if predicted and realized else "FP" if predicted else
                "FN" if realized else "TN")
        group[cell] += 1
        group["total"] += 1
        group["baseline_misses"] += base["background_missed"]
        group["treated_misses"] += treated["background_missed"]
        if cell in ("FP", "FN"):
            which = "false_positive" if cell == "FP" else "false_negative"
            if examples[which] is None and future:
                examples[which] = {
                    "background_remaining_at_request_s": background,
                    "incoming_duration_s": incoming,
                    "future_duration_s": future,
                    "synthetic_deadline_s": deadline,
                    "forecast": predicted,
                    "realized_incremental_miss": realized,
                    "baseline_background_completed_s": base["background_completed_s"],
                    "treated_background_completed_s": treated["background_completed_s"],
                }
    outcomes = {}
    for name, cells in groups.items():
        tp,fp,fn,tn = (cells[k] for k in ("TP","FP","FN","TN"))
        outcomes[name] = {
            "n_scenarios": cells["total"],
            "true_positive": tp, "false_positive": fp,
            "false_negative": fn, "true_negative": tn,
            "accuracy": (tp+tn)/cells["total"] if cells["total"] else None,
            "precision": tp/(tp+fp) if tp+fp else None,
            "recall": tp/(tp+fn) if tp+fn else None,
            "baseline_background_misses": cells["baseline_misses"],
            "override_background_misses": cells["treated_misses"],
        }
    return {
        "protocol": PROTOCOL,
        "plan_sha256": hashlib.sha256(
            json.dumps(plan, sort_keys=True).encode()).hexdigest(),
        "plan": plan,
        "diagnostics": outcomes,
        "counterexamples": examples,
        "evidence_level": "E1",
        "warning": (
            "All experiments are synthetic and fully deterministic; future "
            "arrival violates the projection assumptions. A classifier's "
            "accuracy against its own simulator is NOT external calibration "
            "or proof of operational utility."
        ),
    }


def main():
    print(json.dumps(analyze(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
