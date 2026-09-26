from __future__ import annotations
from .types import Event,AffectiveState
from .state import StateEngine
from .control import ControlPolicy
from .memory import MemoryControl
from .observability import NullTraceSink

class AffectControlHarness:
    def __init__(self,provider,state_engine=None,control=None,memory=None,store=None,trace=None):
        self.provider=provider; self.store=store; self.state_engine=state_engine or StateEngine(); self.control=control or ControlPolicy(); self.memory=memory or MemoryControl(); self.trace=trace or NullTraceSink(); self._states={}
    def _state_for(self,event):
        key=event.scope_key()
        if key is None: return None,AffectiveState()
        if key not in self._states: self._states[key]=(self.store.load(key) if self.store is not None else None) or AffectiveState()
        return key,self._states[key]
    def get_state(self,key):
        if key in self._states: return self._states[key]
        return self.store.load(key) if self.store is not None else None
    def process(self,event:Event,base_priority="P2",integrated=True,relevance=None,recency=None,*,now_s=None):
        key,snapshot=self._state_for(event)
        if event.explicit_user_immediate:
            self.trace.emit("explicit_user_immediate_override",scope_key=key,base_priority=base_priority,effective_priority="P0",interrupt=True)
        try:
            appraisal=self.provider.appraise(event,snapshot)
        except Exception as exc:
            self.trace.emit("appraisal_error",scope_key=key,error_type=type(exc).__name__,message=str(exc)); raise
        if key is not None and self.store is not None:
            state=self.store.update(key,lambda current:self.state_engine.update(current,appraisal,now_s=now_s)); self._states[key]=state
        else: state=self.state_engine.update(snapshot,appraisal,now_s=now_s)
        mem=self.memory.score(state,appraisal,relevance,recency); reflect=self.memory.should_reflect(state,appraisal)
        bias=self.control.evaluate(event,state,appraisal,base_priority=base_priority,integrated=integrated,memory_salience=mem,reflection_trigger=reflect)
        self.trace.emit("control_evaluated",scope_key=key,priority=bias.effective_priority,interrupt=bias.should_interrupt,drive=bias.drive)
        return {"scope_key":key,"appraisal":appraisal,"state":state,"control":bias}
    def outcome(self,key,success,partial=False,*,now_s=None,context=None):
        state=self.get_state(key)
        if state is None: raise KeyError(key)
        fn=lambda current:self.state_engine.reappraise_outcome(current,success,partial,now_s=now_s,context=context)
        state=self.store.update(key,fn) if self.store is not None else fn(state); self._states[key]=state
        self.trace.emit("outcome_reappraised",scope_key=key,success=success,partial=partial); return state
