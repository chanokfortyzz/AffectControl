from __future__ import annotations
import warnings
from .profiles import UncalibratedReferenceWarning
from .config import ControlPolicyConfig
from .features import FeatureMask
from .types import Event,AffectiveState,Appraisal,ControlBias,clamp
RANK={"P0":0,"P1":1,"P2":2,"P3":3}; REV={v:k for k,v in RANK.items()}

def _weighted(values, weights, enabled):
    active={k:v for k,v in weights.items() if k in enabled}
    total=sum(active.values())
    if total<=0: return 0.0
    return sum((w/total)*float(values[k]) for k,w in active.items())

class ControlPolicy:
    def __init__(self,config:ControlPolicyConfig|None=None,*,feature_mask:FeatureMask|None=None):
        if config is None: warnings.warn("ControlPolicy is using uncalibrated reference weights/thresholds",UncalibratedReferenceWarning,stacklevel=2)
        self.config=config or ControlPolicyConfig(); self.feature_mask=feature_mask or FeatureMask.all()
    def evaluate(self,event,state,appraisal,*,base_priority="P2",integrated=True,memory_salience=0.0,reflection_trigger=False):
        base=event.explicit_priority or base_priority; base=base if base in RANK else "P2"
        if event.explicit_user_immediate:
            return ControlBias("P0",True,"high",1.0,memory_salience,reflection_trigger,1.0,1.0,["explicit_user_immediate_hard_override"])
        if not integrated:
            return ControlBias(base,False,"medium",0.0,memory_salience,reflection_trigger,0.0,0.0,["isolated_affect_metadata_only"])
        s=self.feature_mask.state(state); a=self.feature_mask.appraisal(appraisal); c=self.config
        drive=clamp(_weighted({k:getattr(s,k) for k in c.drive_weights},c.drive_weights,self.feature_mask.enabled))
        interrupt=clamp(c.interrupt_appraisal_weight*a.interrupt_value+c.interrupt_state_weight*s.interrupt_value+c.interrupt_drive_weight*drive)
        boost=2 if drive>=c.boost_two_threshold else (1 if drive>=c.boost_one_threshold else 0)
        pr=REV[max(0,RANK[base]-boost)]; should=interrupt>=c.interrupt_threshold or pr=="P0"
        mx=max(s.tension,s.urgency,a.reflection_need); effort="high" if mx>=c.high_effort_threshold else ("medium" if drive>=c.medium_effort_threshold else "low")
        attention=clamp(_weighted({k:getattr(s,k) for k in c.attention_weights},c.attention_weights,self.feature_mask.enabled))
        reasons=[f"feature_mask={self.feature_mask.name}"]
        if boost: reasons.append(f"affective_priority_boost_{boost}")
        if should: reasons.append("interrupt_threshold_exceeded")
        return ControlBias(pr,should,effort,attention,memory_salience,reflection_trigger,drive,interrupt,reasons)
