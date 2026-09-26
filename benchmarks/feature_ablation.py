from __future__ import annotations
import json
from affectcontrol import *

def avg_non_none(values):
    xs=[float(x) for x in values if x is not None]
    return sum(xs)/len(xs) if xs else None



def run(mask, seeds=range(100,200)):
    p=reference_policy(warn=False); rows=[]
    for seed in seeds:
        h=AffectControlHarness(
            KeywordRuleBaseline(p.rule),
            state_engine=StateEngine(p.state),
            control=ControlPolicy(p.control,feature_mask=mask),
            memory=MemoryControl(p.memory,feature_mask=mask),
        )
        s=AffectiveScheduler(p.scheduler,strategy="affective")
        rows.append(TraceRunner(h,s).run(semi_synthetic_workflow(seed)))
    keys=("deadline_miss_rate","wrong_preemption_rate","task_thrashing","user_override_compliance","completion_rate")
    return {k:avg_non_none([r[k] for r in rows]) for k in keys}


def main():
    masks=[FeatureMask.all(),FeatureMask.minimal(),*leave_one_out_masks()]
    print(json.dumps({m.name:run(m) for m in masks},indent=2,sort_keys=True))

if __name__=="__main__": main()
