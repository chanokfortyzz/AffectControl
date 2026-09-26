from __future__ import annotations
from dataclasses import dataclass, field
from math import isclose

def _unit_weights(name, values):
    if any(v < 0 for v in values.values()) or not isclose(sum(values.values()),1.0,abs_tol=1e-9):
        raise ValueError(f"{name} weights must be non-negative and sum to 1")

def _prob(name, value):
    if not 0 <= value <= 1: raise ValueError(f"{name} must be in [0,1]")



@dataclass(frozen=True, slots=True)
class RuleProviderConfig:
    routine_urgency: float = 0.30
    urgent_urgency: float = 0.78
    routine_salience: float = 0.40
    urgent_salience: float = 0.62
    immediate_salience: float = 0.90
    routine_arousal: float = 0.30
    urgent_arousal: float = 0.62
    immediate_arousal: float = 0.88
    punctuation_arousal_step: float = 0.02
    punctuation_arousal_cap: float = 0.08
    routine_tension: float = 0.35
    urgent_tension: float = 0.86
    routine_interrupt: float = 0.20
    urgent_interrupt: float = 0.68
    routine_memory: float = 0.42
    urgent_memory: float = 0.72
    default_interest: float = 0.50
    default_certainty: float = 0.75
    default_competence: float = 0.55
    user_goal_relevance: float = 0.85
    nonuser_goal_relevance: float = 0.50
    urgent_expected_impact: float = 0.75
    routine_expected_impact: float = 0.45
    default_reflection_need: float = 0.35

@dataclass(frozen=True, slots=True)
class StateConfig:
    """Uncalibrated reference priors. Replace or fit for real experiments."""
    alpha: float = 0.55
    half_life_s: dict[str, float] = field(default_factory=lambda: {
        "urgency": 1800.0,
        "salience": 7200.0,
        "arousal": 3600.0,
        "interest": 21600.0,
        "tension": 14400.0,
        "goal_activation": 14400.0,
        "interrupt_value": 1800.0,
        "memory_value": 43200.0,
    })
    success_tension_factor: float = 0.30
    partial_success_tension_factor: float = 0.65
    success_urgency_factor: float = 0.55
    success_competence_delta: float = 0.12
    success_certainty_delta: float = 0.08
    failure_tension_delta: float = 0.18
    failure_salience_delta: float = 0.10
    failure_competence_delta: float = -0.08
    certainty_half_life_s: float = 7200.0
    competence_half_life_s: float = 21600.0
    def __post_init__(self):
        _prob("alpha",self.alpha)
        if any(v <= 0 for v in self.half_life_s.values()) or self.certainty_half_life_s <= 0 or self.competence_half_life_s <= 0: raise ValueError("half-lives must be positive")
        for name in ("success_tension_factor","partial_success_tension_factor","success_urgency_factor"): _prob(name,getattr(self,name))

@dataclass(frozen=True, slots=True)
class MemoryPolicyConfig:
    affect_weights: dict[str, float] = field(default_factory=lambda: {
        "salience": 0.35, "arousal": 0.15, "interest": 0.15, "state_memory_value": 0.20, "appraisal_memory_value": 0.15,
    })
    retrieval_weights: dict[str, float] = field(default_factory=lambda: {
        "affect": 0.45, "relevance": 0.35, "recency": 0.20,
    })
    reflection_weights: dict[str, float] = field(default_factory=lambda: {
        "tension": 0.60, "salience": 0.25, "reflection_need": 0.15,
    })
    reflection_threshold: float = 0.75
    default_relevance: float = 0.50
    default_recency: float = 0.50
    def __post_init__(self):
        _unit_weights("affect",self.affect_weights); _unit_weights("retrieval",self.retrieval_weights); _unit_weights("reflection",self.reflection_weights); _prob("reflection_threshold",self.reflection_threshold); _prob("default_relevance",self.default_relevance); _prob("default_recency",self.default_recency)

@dataclass(frozen=True, slots=True)
class ControlPolicyConfig:
    drive_weights: dict[str, float] = field(default_factory=lambda: {
        "urgency": 0.25, "salience": 0.18, "arousal": 0.12, "interest": 0.10, "tension": 0.18, "goal_activation": 0.17,
    })
    interrupt_appraisal_weight: float = 0.40
    interrupt_state_weight: float = 0.25
    interrupt_drive_weight: float = 0.35
    interrupt_threshold: float = 0.72
    boost_one_threshold: float = 0.52
    boost_two_threshold: float = 0.82
    high_effort_threshold: float = 0.80
    medium_effort_threshold: float = 0.45
    attention_weights: dict[str, float] = field(default_factory=lambda: {
        "salience": 0.55, "urgency": 0.25, "arousal": 0.20,
    })
    def __post_init__(self):
        _unit_weights("drive",self.drive_weights); _unit_weights("attention",self.attention_weights)
        _unit_weights("interrupt",{"appraisal":self.interrupt_appraisal_weight,"state":self.interrupt_state_weight,"drive":self.interrupt_drive_weight})
        for name in ("interrupt_threshold","boost_one_threshold","boost_two_threshold","high_effort_threshold","medium_effort_threshold"): _prob(name,getattr(self,name))
        if self.boost_two_threshold < self.boost_one_threshold: raise ValueError("boost_two_threshold must be >= boost_one_threshold")

@dataclass(frozen=True, slots=True)
class SchedulerConfig:
    quantum_s: float = 1.0
    priority_weight: float = 1.0
    affect_weight: float = 1.0
    deadline_weight: float = 1.0
    deadline_horizon_s: float = 60.0
    switch_penalty: float = 0.12
    preempt_margin: float = 0.15
    thrash_window_s: float = 30.0
    thrash_preemptions: int = 3
    def __post_init__(self):
        if self.quantum_s <= 0 or self.deadline_horizon_s <= 0 or self.thrash_window_s <= 0: raise ValueError("scheduler time parameters must be positive")
        if min(self.priority_weight,self.affect_weight,self.deadline_weight,self.switch_penalty,self.preempt_margin) < 0: raise ValueError("scheduler weights/penalties must be non-negative")
        if self.thrash_preemptions < 2: raise ValueError("thrash_preemptions must be >= 2")
