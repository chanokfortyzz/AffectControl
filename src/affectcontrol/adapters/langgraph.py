from __future__ import annotations
from dataclasses import dataclass
from ..types import Event

@dataclass(slots=True)
class LangGraphControlNode:
    """Callable node helper for graph state dictionaries.

    The returned mapping can be merged into LangGraph state by the graph runtime.
    No LangGraph dependency is imported by core AffectControl.
    """
    harness: object
    text_key: str = "input"
    task_id_key: str = "task_id"
    immediate_key: str = "explicit_user_immediate"
    output_key: str = "affectcontrol"

    def __call__(self, state: dict) -> dict:
        result=self.harness.process(Event(
            str(state.get(self.text_key,"")),
            task_id=str(state.get(self.task_id_key) or "") or None,
            explicit_user_immediate=bool(state.get(self.immediate_key,False)),
        ),base_priority=str(state.get("priority","P2")))
        return {self.output_key:{"scope_key":result["scope_key"],"control":result["control"].asdict(),"state":result["state"].asdict()}}
