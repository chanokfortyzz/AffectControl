from __future__ import annotations
from .config import ControlPolicyConfig
from .types import Event, AffectiveState, Appraisal, ControlBias, clamp
RANK={"P0":0,"P1":1,"P2":2,"P3":3}; REV={v:k for k,v in RANK.items()}

class ControlPolicy:
    def __init__(self, config: ControlPolicyConfig | None = None): self.config=config or ControlPolicyConfig()
    def evaluate(self, event: Event, state: AffectiveState, appraisal: Appraisal, *, base_priority: str="P2", integrated: bool=True,
                 memory_salience: float=0.0, reflection_trigger: bool=False) -> ControlBias:
        base=event.explicit_priority or base_priority; base=base if base in RANK else "P2"
        if event.explicit_user_immediate:
            return ControlBias("P0",True,"high",1.0,memory_salience,reflection_trigger,1.0,1.0,["explicit_user_immediate_hard_override"])
        if not integrated:
            return ControlBias(base,False,"medium",0.0,memory_salience,reflection_trigger,0.0,0.0,["isolated_affect_metadata_only"])
        c=self.config; w=c.drive_weights
        drive=clamp(sum(w[k]*getattr(state,k) for k in w))
        interrupt=clamp(c.interrupt_appraisal_weight*appraisal.interrupt_value+c.interrupt_state_weight*state.interrupt_value+c.interrupt_drive_weight*drive)
        boost=2 if drive>=c.boost_two_threshold else (1 if drive>=c.boost_one_threshold else 0)
        pr=REV[max(0,RANK[base]-boost)]
        should=interrupt>=c.interrupt_threshold or pr=="P0"
        mx=max(state.tension,state.urgency,appraisal.reflection_need)
        effort="high" if mx>=c.high_effort_threshold else ("medium" if drive>=c.medium_effort_threshold else "low")
        aw=c.attention_weights; attention=clamp(sum(aw[k]*getattr(state,k) for k in aw))
        reasons=[]
        if boost: reasons.append(f"affective_priority_boost_{boost}")
        if should: reasons.append("interrupt_threshold_exceeded")
        return ControlBias(pr,should,effort,attention,memory_salience,reflection_trigger,drive,interrupt,reasons or ["no_affective_escalation"])
