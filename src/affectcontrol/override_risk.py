"""Conservative displaced-task deadline projection for research-only audits.

This is a conditional, single-processor *projection* under fixed remaining
durations and uninterrupted handling of the explicit user request. It is not
an actual deadline outcome, an authorization decision, or a policy change.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

from .types import TaskRecord


@dataclass(frozen=True, slots=True)
class OverrideRisk:
    status: str
    reference_time_s: float
    deadline_s: float | None
    deadline_basis: str
    projected_finish_no_override_s: float | None
    projected_finish_with_override_s: float | None
    additional_delay_s: float | None
    newly_projected_deadline_miss: bool | None
    predictive_scope: str = "conditional_on_no_future_arrivals"
    external_calibration_status: str = "unvalidated"
    assumption: str = (
        "One work resource, fixed remaining durations, no other arrivals, "
        "zero switch cost, immediate uninterrupted execution of incoming task. "
        "Not externally observed or independently verified."
    )

    def asdict(self) -> dict:
        return asdict(self)


def projected_override_risk(now_s: float, displaced: TaskRecord,
                            incoming: TaskRecord) -> OverrideRisk:
    """Project only the task displaced by a user-immediate preemption.

    Missing/invalid deadlines or durations are explicitly unknown. A
    projection does not suppress an explicit user instruction or equate
    unspecified provenance with a verified customer deadline.
    """
    basis = displaced.spec.metadata.get("deadline_basis", "unspecified")
    if basis not in ("observed", "inferred", "synthetic", "unspecified"):
        basis = "unspecified"
    deadline = displaced.spec.deadline_s
    if deadline is None:
        return OverrideRisk("no_deadline", now_s, None, basis,
                            None, None, None, None)
    try:
        numbers = [float(now_s), float(deadline),
                   float(displaced.remaining_s), float(incoming.remaining_s)]
    except (ValueError, TypeError, OverflowError):
        return OverrideRisk("unquantifiable", now_s, None, basis,
                            None, None, None, None)
    if not all(math.isfinite(x) for x in numbers) or numbers[2] < 0 or numbers[3] < 0:
        return OverrideRisk("unquantifiable", now_s, None, basis,
                            None, None, None, None)
    now, end, displaced_left, incoming_left = numbers
    no_override = now + displaced_left
    with_override = now + incoming_left + displaced_left
    if no_override > end:
        status = "already_projected_miss"
    elif with_override > end:
        status = "newly_projected_miss"
    else:
        status = "no_new_projected_miss"
    return OverrideRisk(status, now, end, basis, no_override,
                        with_override, incoming_left,
                        status == "newly_projected_miss")
