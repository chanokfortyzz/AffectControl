from __future__ import annotations
from dataclasses import dataclass
from ..types import Event

@dataclass(slots=True)
class CrewAIFlowControlBridge:
    """Helper for Flow/Crew application state; not a CrewAI authorization layer."""
    harness: object
    def appraise_flow_event(self, text: str, *, flow_id: str|None=None, immediate: bool=False, priority: str="P2") -> dict:
        r=self.harness.process(Event(text,goal_id=flow_id,explicit_user_immediate=immediate),base_priority=priority)
        return {"scope_key":r["scope_key"],"control":r["control"].asdict(),"state":r["state"].asdict()}
