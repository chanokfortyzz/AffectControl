from __future__ import annotations
import json
from affectcontrol import *

def avg_non_none(values):
    xs=[float(x) for x in values if x is not None]
    return sum(xs)/len(xs) if xs else None


FEATURES=("urgency","salience","tension","interrupt_value","priority","deadline_pressure")
RANK={"P0":1.0,"P1":.75,"P2":.5,"P3":.25}

def examples(seeds):
    p=reference_policy(warn=False); provider=KeywordRuleBaseline(p.rule); rows=[]; labels=[]
    for seed in seeds:
        trace=semi_synthetic_workflow(seed)
        for event in trace.events:
            if event.kind!="arrive": continue
            q=event.payload; priority=str(q.get("priority","P2")); deadline=q.get("deadline_s")
            a=provider.appraise(Event(str(q.get("text",event.task_id)),task_id=event.task_id,explicit_user_immediate=bool(q.get("immediate",False))))
            pressure=0.0 if deadline is None else 1/(1+max(0,float(deadline)-event.at_s)/60)
            rows.append({"urgency":a.urgency,"salience":a.salience,"tension":a.tension,"interrupt_value":a.interrupt_value,"priority":RANK.get(priority,.5),"deadline_pressure":pressure})
            labels.append(1 if q.get("expected_interrupt",q.get("immediate",False)) else 0)
    return rows,labels

def evaluate(strategy,model=None,seeds=range(100,300)):
    p=reference_policy(warn=False); out=[]
    for seed in seeds:
        h=AffectControlHarness(KeywordRuleBaseline(p.rule),state_engine=StateEngine(p.state),control=ControlPolicy(p.control),memory=MemoryControl(p.memory))
        s=AffectiveScheduler(p.scheduler,strategy=strategy)
        out.append(TraceRunner(h,s,interrupt_model=model).run(semi_synthetic_workflow(seed)))
    keys=("deadline_miss_rate","wrong_preemption_rate","task_thrashing","user_override_compliance","completion_rate","preemptions")
    return {k:avg_non_none([r[k] for r in out]) for k in keys}

def main():
    x,y=examples(range(0,100)); model=LogisticInterruptionModel(FEATURES).fit(x,y)
    report={s:evaluate(s,model if s=="learned" else None) for s in ("static","edf","urgency","learned","affective")}
    report["learned_model"]={"features":FEATURES,"weights":model.weights,"bias":model.bias,"train_n":len(y),"test_seed_range":[100,299]}
    print(json.dumps(report,indent=2,sort_keys=True))

if __name__=="__main__": main()
