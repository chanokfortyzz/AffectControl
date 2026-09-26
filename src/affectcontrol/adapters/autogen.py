from __future__ import annotations
from dataclasses import dataclass
from ..types import Event

@dataclass(slots=True)
class AutoGenControlBridge:
    """Framework-neutral bridge around AutoGen-style task/message calls.

    Call `before_run` before `AssistantAgent.run()`/equivalent in the host application.
    This helper intentionally does not monkey-patch AutoGen internals.
    """
    harness: object
    def before_run(self, task: str, *, task_id: str|None=None, immediate: bool=False, priority: str="P2") -> dict:
        r=self.harness.process(Event(task,task_id=task_id,explicit_user_immediate=immediate),base_priority=priority)
        return {"scope_key":r["scope_key"],"control":r["control"].asdict(),"state":r["state"].asdict()}
