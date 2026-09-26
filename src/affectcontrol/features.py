from __future__ import annotations
from dataclasses import dataclass, replace
from .types import AffectiveState, Appraisal

CANDIDATE_STATE_FEATURES = (
    "urgency", "salience", "arousal", "interest", "tension",
    "goal_activation", "interrupt_value", "memory_value", "certainty", "competence",
)

@dataclass(frozen=True, slots=True)
class FeatureMask:
    enabled: frozenset[str]
    name: str = "custom"
    def __post_init__(self):
        unknown=set(self.enabled)-set(CANDIDATE_STATE_FEATURES)
        if unknown:
            raise ValueError(f"unknown candidate features: {sorted(unknown)}")
    @classmethod
    def all(cls):
        return cls(frozenset(CANDIDATE_STATE_FEATURES), "all-candidate-features")
    @classmethod
    def minimal(cls):
        return cls(frozenset({"urgency","tension","goal_activation","certainty"}), "minimal-candidate-set")
    def state(self, value: AffectiveState) -> AffectiveState:
        out=replace(value)
        for key in CANDIDATE_STATE_FEATURES:
            if key not in self.enabled:
                setattr(out,key,0.5 if key in {"certainty","competence"} else 0.0)
        return out
    def appraisal(self, value: Appraisal) -> Appraisal:
        out=replace(value, raw=dict(value.raw))
        for key in CANDIDATE_STATE_FEATURES:
            if hasattr(out,key) and key not in self.enabled:
                setattr(out,key,0.5 if key in {"certainty","competence"} else 0.0)
        return out

def leave_one_out_masks():
    all_features=set(CANDIDATE_STATE_FEATURES)
    return [FeatureMask(frozenset(all_features-{name}), f"minus-{name}") for name in CANDIDATE_STATE_FEATURES]
