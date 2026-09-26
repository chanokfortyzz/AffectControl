from __future__ import annotations
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

def clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))

@dataclass(slots=True)
class Event:
    text: str
    kind: str = "user"
    explicit_user_immediate: bool = False
    explicit_priority: str | None = None
    task_id: str | None = None
    goal_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    def scope_key(self) -> str | None:
        return self.task_id or self.metadata.get("task_id") or self.goal_id or self.metadata.get("goal_id")

@dataclass(slots=True)
class Appraisal:
    urgency: float = 0.0
    salience: float = 0.0
    arousal: float = 0.0
    interest: float = 0.0
    tension: float = 0.0
    goal_activation: float = 0.0
    interrupt_value: float = 0.0
    memory_value: float = 0.0
    certainty: float = 0.5
    competence: float = 0.5
    goal_relevance: float = 0.0
    expected_impact: float = 0.0
    reflection_need: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)
    def normalized(self) -> "Appraisal":
        for k in self.__dataclass_fields__:
            if k != "raw": setattr(self, k, clamp(getattr(self, k)))
        return self

@dataclass(slots=True)
class AffectiveState:
    urgency: float = 0.0
    salience: float = 0.0
    arousal: float = 0.0
    interest: float = 0.0
    tension: float = 0.0
    goal_activation: float = 0.0
    interrupt_value: float = 0.0
    memory_value: float = 0.0
    certainty: float = 0.5
    competence: float = 0.5
    last_update_s: float = 0.0
    step: int = 0
    def asdict(self) -> dict[str, Any]: return asdict(self)

@dataclass(slots=True)
class ControlBias:
    effective_priority: str = "P2"
    should_interrupt: bool = False
    planning_effort: str = "medium"
    attention_weight: float = 0.0
    memory_salience: float = 0.0
    reflection_trigger: bool = False
    drive: float = 0.0
    interrupt_score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    def asdict(self) -> dict[str, Any]: return asdict(self)

class TaskStatus(str, Enum):
    QUEUED="queued"; RUNNING="running"; PAUSED="paused"; DONE="done"; FAILED="failed"; CANCELLED="cancelled"

@dataclass(slots=True)
class TaskSpec:
    task_id: str
    text: str
    duration_s: float
    base_priority: str = "P2"
    created_at_s: float = 0.0
    deadline_s: float | None = None
    preemptible: bool = True
    goal_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class TaskRecord:
    spec: TaskSpec
    status: TaskStatus = TaskStatus.QUEUED
    remaining_s: float = 0.0
    started_at_s: float | None = None
    completed_at_s: float | None = None
    paused_at_s: float | None = None
    resume_count: int = 0
    control: ControlBias = field(default_factory=ControlBias)
    interrupt_requested_at_s: float | None = None
    def __post_init__(self):
        if self.remaining_s <= 0: self.remaining_s = float(self.spec.duration_s)
