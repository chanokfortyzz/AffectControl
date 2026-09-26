from __future__ import annotations
import warnings
from .profiles import UncalibratedReferenceWarning
from dataclasses import replace
from .clock import SystemClock
from .config import StateConfig
from .dynamics import ReferenceExponentialDynamics
from .types import AffectiveState, Appraisal, clamp

class StateEngine:
    def __init__(self, config: StateConfig | None = None, *, half_life_s: float | None = None, alpha: float | None = None, clock=None, dynamics=None):
        if config is None: warnings.warn("StateEngine is using uncalibrated reference dynamics/config",UncalibratedReferenceWarning,stacklevel=2)
        cfg=config or StateConfig()
        if half_life_s is not None: cfg=replace(cfg,half_life_s={k:half_life_s for k in cfg.half_life_s})
        if alpha is not None: cfg=replace(cfg,alpha=alpha)
        self.config=cfg; self.clock=clock or SystemClock(); self.dynamics=dynamics or ReferenceExponentialDynamics()
    def decay(self,state:AffectiveState,now_s:float|None=None)->AffectiveState:
        now=self.clock.now() if now_s is None else float(now_s)
        if state.step == 0 and state.last_update_s == 0.0: state.last_update_s=now; return state
        dt=max(0.0,now-state.last_update_s); self.dynamics.decay(state,dt,self.config); state.last_update_s=now; return state
    def update(self,state:AffectiveState,appraisal:Appraisal,now_s:float|None=None)->AffectiveState:
        now=self.clock.now() if now_s is None else float(now_s); self.decay(state,now); appraisal.normalized(); w=self.config.alpha
        for key in ("urgency","salience","arousal","interest","tension","goal_activation","interrupt_value","memory_value","certainty","competence"):
            setattr(state,key,clamp((1-w)*getattr(state,key)+w*getattr(appraisal,key)))
        state.step+=1; state.last_update_s=now; return state
    def reappraise_outcome(self,state:AffectiveState,success:bool,partial:bool=False,*,now_s:float|None=None,context:dict|None=None)->AffectiveState:
        now=self.clock.now() if now_s is None else float(now_s); self.decay(state,now)
        self.dynamics.outcome(state,success,partial,self.config,context); state.step+=1; state.last_update_s=now; return state
