from __future__ import annotations
from typing import Protocol
from .types import AffectiveState, clamp
from .config import StateConfig

class DynamicsModel(Protocol):
    def decay(self, state: AffectiveState, dt_s: float, config: StateConfig) -> AffectiveState: ...
    def outcome(self, state: AffectiveState, success: bool, partial: bool, config: StateConfig, context: dict | None = None) -> AffectiveState: ...

class ReferenceExponentialDynamics:
    """Uncalibrated reference dynamics used only as an experimental baseline."""
    def decay(self,state,dt_s,config):
        for key,half in config.half_life_s.items():
            if hasattr(state,key):
                setattr(state,key,clamp(getattr(state,key)*(0.5 ** (dt_s/half))))
        state.certainty=clamp(0.5+(state.certainty-0.5)*(0.5 ** (dt_s/config.certainty_half_life_s)))
        state.competence=clamp(0.5+(state.competence-0.5)*(0.5 ** (dt_s/config.competence_half_life_s)))
        return state
    def outcome(self,state,success,partial,config,context=None):
        importance=float((context or {}).get("importance",1.0))
        importance=max(0.0,min(1.0,importance))
        if success:
            factor=config.partial_success_tension_factor if partial else config.success_tension_factor
            state.tension=clamp(state.tension*(1-(1-factor)*importance))
            state.urgency=clamp(state.urgency*(1-(1-config.success_urgency_factor)*importance))
            state.competence=clamp(state.competence+config.success_competence_delta*importance)
            state.certainty=clamp(state.certainty+config.success_certainty_delta*importance)
        else:
            state.tension=clamp(state.tension+config.failure_tension_delta*importance)
            state.salience=clamp(state.salience+config.failure_salience_delta*importance)
            state.competence=clamp(state.competence+config.failure_competence_delta*importance)
        return state

class NoDecayDynamics(ReferenceExponentialDynamics):
    def decay(self,state,dt_s,config):
        return state
