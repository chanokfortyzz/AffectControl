"""Fail-closed *operational* triage separate from uncalibrated affect scores.

Context values are supplied by a caller, not inferred from natural language.
The gate never authorizes dispatch. Missing context means abstain, not 'safe'.
"""
from __future__ import annotations

import math
from typing import Any

_ALLOWED = frozenset({
    "current_task_running", "current_task_preemptible", "task_blocked",
    "seconds_until_deadline", "estimated_work_seconds",
})
_REQUIRED = (
    "current_task_running", "current_task_preemptible", "task_blocked",
    "seconds_until_deadline", "estimated_work_seconds",
)


def normalize_context(raw: Any) -> dict[str, bool | float] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("context must be a JSON object")
    unknown = set(raw).difference(_ALLOWED)
    if unknown:
        raise ValueError("context contains unknown fields: " + ", ".join(sorted(map(str, unknown))))
    clean: dict[str, bool | float] = {}
    for key, value in raw.items():
        if key in {"current_task_running", "current_task_preemptible", "task_blocked"}:
            if type(value) is not bool:
                raise ValueError(f"context.{key} must be boolean")
            clean[key] = value
        else:
            if type(value) not in (float, int):
                raise ValueError(f"context.{key} must be finite number")
            if value < 0 or value > 31_536_000 or (type(value) is float and not math.isfinite(value)):
                raise ValueError(f"context.{key} outside accepted 0..31536000 range")
            clean[key] = float(value)
    return clean


def assess_context(raw: Any, *, explicit_user_immediate: bool = False) -> dict:
    """A deadline-only independent comparator; no self-calibration or authority.

    This is not the affective policy. It is a context/permission quality gate.
    """
    ctx = normalize_context(raw) or {}
    missing = [key for key in _REQUIRED if key not in ctx]
    result = {
        "name": "deadline_context_gate_v1",
        "mode": "shadow", "dispatch_allowed": False,
        "context_supplied": bool(ctx),
        "missing_fields": missing,
        "verdict": "abstain",
        "would_interrupt": None,
        "deadline_slack_s": None,
        "reasons": [],
    }
    if missing:
        result["reasons"] = ["insufficient_structured_context"]
        return result
    result["deadline_slack_s"] = round(
        ctx["seconds_until_deadline"] - ctx["estimated_work_seconds"], 6)
    if ctx["task_blocked"]:
        result["verdict"] = "blocked_task"
        result["would_interrupt"] = False
        result["reasons"] = ["task_dependency_blocked"]
    elif not ctx["current_task_running"]:
        result["verdict"] = "no_active_task"
        result["would_interrupt"] = False
        result["reasons"] = ["no_running_task_to_preempt"]
    elif not ctx["current_task_preemptible"]:
        result["verdict"] = "safety_hold"
        result["would_interrupt"] = False
        result["reasons"] = ["current_task_not_preemptible"]
    elif explicit_user_immediate:
        result["verdict"] = "propose_interrupt"
        result["would_interrupt"] = True
        result["reasons"] = ["explicit_user_immediate_hard_priority_override"]
    elif result["deadline_slack_s"] <= 0:
        result["verdict"] = "propose_interrupt"
        result["would_interrupt"] = True
        result["reasons"] = ["deadline_infeasible_under_estimate"]
    else:
        result["verdict"] = "do_not_interrupt"
        result["would_interrupt"] = False
        result["reasons"] = ["deadline_slack_positive"]
    return result
