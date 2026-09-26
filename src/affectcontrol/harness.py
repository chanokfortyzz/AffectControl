from __future__ import annotations
from .types import Event, AffectiveState
from .state import StateEngine
from .control import ControlPolicy
from .memory import MemoryControl

class AffectControlHarness:
    """Per-task/per-goal affective controller.

    Events without a task_id/goal_id are transient by design: they do not share a
    global state vector, preventing cross-task contamination.
    """
    def __init__(self,provider,state_engine=None,control=None,memory=None,store=None):
        self.provider=provider; self.store=store
        self.state_engine=state_engine or StateEngine(); self.control=control or ControlPolicy(); self.memory=memory or MemoryControl()
        self._states: dict[str,AffectiveState]={}
    def _state_for(self,event:Event) -> tuple[str|None,AffectiveState]:
        key=event.scope_key()
        if key is None: return None,AffectiveState()
        if key not in self._states:
            self._states[key]=(self.store.load(key) if self.store is not None else None) or AffectiveState()
        return key,self._states[key]
    def get_state(self,key:str)->AffectiveState|None:
        if key in self._states: return self._states[key]
        return self.store.load(key) if self.store is not None else None
    def process(self,event:Event,base_priority="P2",integrated=True,relevance:float|None=None,recency:float|None=None):
        key,snapshot=self._state_for(event); appraisal=self.provider.appraise(event,snapshot)
        if key is not None and self.store is not None:
            state=self.store.update(key, lambda current: self.state_engine.update(current,appraisal)); self._states[key]=state
        else:
            state=self.state_engine.update(snapshot,appraisal)
        mem=self.memory.score(state,appraisal,relevance,recency); reflect=self.memory.should_reflect(state,appraisal)
        bias=self.control.evaluate(event,state,appraisal,base_priority=base_priority,integrated=integrated,memory_salience=mem,reflection_trigger=reflect)
        return {"scope_key":key,"appraisal":appraisal,"state":state,"control":bias}
    def outcome(self,key:str,success:bool,partial:bool=False):
        state=self.get_state(key)
        if state is None: raise KeyError(key)
        if self.store is not None:
            state=self.store.update(key, lambda current: self.state_engine.reappraise_outcome(current,success,partial))
        else:
            state=self.state_engine.reappraise_outcome(state,success,partial)
        self._states[key]=state; return state
