from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(slots=True)
class GlobalControlContext:
    """Non-affective cross-task context. It is separate from per-task affect state."""
    goal_weights: dict[str,float]=field(default_factory=dict)
    resource_pressure: float=0.0
    def task_adjustment(self, goal_id: str | None) -> float:
        if not goal_id: return 0.0
        return float(self.goal_weights.get(goal_id,0.0))
