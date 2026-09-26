from __future__ import annotations
from .config import MemoryPolicyConfig
from .types import AffectiveState, Appraisal, clamp

class MemoryControl:
    def __init__(self, config: MemoryPolicyConfig | None = None): self.config = config or MemoryPolicyConfig()
    def score(self, state: AffectiveState, appraisal: Appraisal, relevance: float | None = None, recency: float | None = None) -> float:
        relevance=self.config.default_relevance if relevance is None else relevance; recency=self.config.default_recency if recency is None else recency
        aw=self.config.affect_weights
        affect = (aw["salience"]*state.salience + aw["arousal"]*state.arousal + aw["interest"]*state.interest + aw["state_memory_value"]*state.memory_value + aw["appraisal_memory_value"]*appraisal.memory_value)
        rw=self.config.retrieval_weights
        return clamp(rw["affect"]*affect + rw["relevance"]*relevance + rw["recency"]*recency)
    def should_reflect(self, state: AffectiveState, appraisal: Appraisal) -> bool:
        w=self.config.reflection_weights
        score=w["tension"]*state.tension+w["salience"]*state.salience+w["reflection_need"]*appraisal.reflection_need
        return score >= self.config.reflection_threshold
