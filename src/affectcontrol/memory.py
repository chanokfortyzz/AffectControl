from __future__ import annotations
import warnings
from .profiles import UncalibratedReferenceWarning
from .config import MemoryPolicyConfig
from .features import FeatureMask
from .types import AffectiveState,Appraisal,clamp

class MemoryControl:
    def __init__(self,config:MemoryPolicyConfig|None=None,*,feature_mask:FeatureMask|None=None):
        if config is None: warnings.warn("MemoryControl is using uncalibrated reference weights/thresholds",UncalibratedReferenceWarning,stacklevel=2)
        self.config=config or MemoryPolicyConfig(); self.feature_mask=feature_mask or FeatureMask.all()
    def score(self,state,appraisal,relevance=None,recency=None):
        s=self.feature_mask.state(state); a=self.feature_mask.appraisal(appraisal); c=self.config
        relevance=c.default_relevance if relevance is None else relevance; recency=c.default_recency if recency is None else recency
        aw=c.affect_weights; affect=(aw['salience']*s.salience+aw['arousal']*s.arousal+aw['interest']*s.interest+aw['state_memory_value']*s.memory_value+aw['appraisal_memory_value']*a.memory_value)
        rw=c.retrieval_weights; return clamp(rw['affect']*affect+rw['relevance']*relevance+rw['recency']*recency)
    def should_reflect(self,state,appraisal):
        s=self.feature_mask.state(state); a=self.feature_mask.appraisal(appraisal); w=self.config.reflection_weights
        return w['tension']*s.tension+w['salience']*s.salience+w['reflection_need']*a.reflection_need >= self.config.reflection_threshold
