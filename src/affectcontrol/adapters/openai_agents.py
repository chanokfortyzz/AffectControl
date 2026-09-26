from __future__ import annotations
from dataclasses import dataclass,field
from ..types import Event

@dataclass(slots=True)
class OpenAIAgentsContext:
    """Application context payload suitable for Runner.run(..., context=...)."""
    task_id: str|None=None
    affectcontrol: dict=field(default_factory=dict)
    metadata: dict=field(default_factory=dict)

def apply_to_openai_context(harness, context: OpenAIAgentsContext, text: str, *, immediate: bool=False, priority: str="P2"):
    result=harness.process(Event(text,task_id=context.task_id,explicit_user_immediate=immediate),base_priority=priority)
    context.affectcontrol={"scope_key":result["scope_key"],"control":result["control"].asdict(),"state":result["state"].asdict()}
    return context
