from __future__ import annotations
from collections.abc import Mapping
from ..types import Event

VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}

def event_from_task(task: Mapping) -> Event:
    priority = str(task.get("priority") or "").upper()
    immediate = bool(
        task.get("explicit_user_immediate")
        or task.get("immediate")
        or str(task.get("execution_mode") or "").lower() == "immediate"
    )
    text = " ".join(str(task.get(k) or "") for k in ("title", "description", "scope"))
    return Event(
        text=text,
        kind=str(task.get("source") or "task"),
        explicit_user_immediate=immediate,
        explicit_priority=priority if priority in VALID_PRIORITIES else None,
        task_id=str(task.get("task_id")) if task.get("task_id") is not None else None,
        goal_id=str(task.get("goal_id")) if task.get("goal_id") is not None else None,
        metadata={},
    )

def apply_control_to_task(task: Mapping, control) -> dict:
    out = dict(task)
    out.update({
        "effective_priority": control.effective_priority,
        "should_interrupt": control.should_interrupt,
        "planning_effort": control.planning_effort,
        "attention_weight": control.attention_weight,
        "memory_salience": control.memory_salience,
        "reflection_trigger": control.reflection_trigger,
    })
    return out
