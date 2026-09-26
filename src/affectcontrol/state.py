from __future__ import annotations
import time
from dataclasses import replace
from .config import StateConfig
from .types import AffectiveState, Appraisal, clamp

class StateEngine:
    def __init__(self, config: StateConfig | None = None, *, half_life_s: float | None = None, alpha: float | None = None):
        cfg = config or StateConfig()
        if half_life_s is not None:
            cfg = replace(cfg, half_life_s={k: half_life_s for k in cfg.half_life_s})
        if alpha is not None:
            cfg = replace(cfg, alpha=alpha)
        self.config = cfg
    def decay(self, state: AffectiveState, now_s: float | None = None) -> AffectiveState:
        now = time.time() if now_s is None else now_s
        if not state.last_update_s:
            state.last_update_s = now; return state
        dt = max(0.0, now - state.last_update_s)
        for k, half in self.config.half_life_s.items():
            if hasattr(state, k):
                factor = 0.5 ** (dt / half) if half > 0 else 0.0
                setattr(state, k, clamp(getattr(state, k) * factor))
        state.certainty = clamp(0.5 + (state.certainty - 0.5) * (0.5 ** (dt / self.config.certainty_half_life_s)))
        state.competence = clamp(0.5 + (state.competence - 0.5) * (0.5 ** (dt / self.config.competence_half_life_s)))
        state.last_update_s = now; return state
    def update(self, state: AffectiveState, appraisal: Appraisal, now_s: float | None = None) -> AffectiveState:
        now = time.time() if now_s is None else now_s
        self.decay(state, now); appraisal.normalized(); w = self.config.alpha
        pairs = {"urgency":"urgency","salience":"salience","arousal":"arousal","interest":"interest","tension":"tension",
                 "goal_activation":"goal_activation","interrupt_value":"interrupt_value","memory_value":"memory_value",
                 "certainty":"certainty","competence":"competence"}
        for sk, ak in pairs.items(): setattr(state, sk, clamp((1-w)*getattr(state,sk)+w*getattr(appraisal,ak)))
        state.step += 1; state.last_update_s = now; return state
    def reappraise_outcome(self, state: AffectiveState, success: bool, partial: bool = False) -> AffectiveState:
        c = self.config
        if success:
            state.tension = clamp(state.tension * (c.partial_success_tension_factor if partial else c.success_tension_factor))
            state.urgency = clamp(state.urgency * c.success_urgency_factor)
            state.competence = clamp(state.competence + c.success_competence_delta)
            state.certainty = clamp(state.certainty + c.success_certainty_delta)
        else:
            state.tension = clamp(state.tension + c.failure_tension_delta)
            state.salience = clamp(state.salience + c.failure_salience_delta)
            state.competence = clamp(state.competence + c.failure_competence_delta)
        state.step += 1; return state
