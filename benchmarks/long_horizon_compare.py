from __future__ import annotations
import argparse,json
from affectcontrol import AffectControlHarness,AffectiveScheduler,RuleProvider,TraceRunner,mean_ci95,semi_synthetic_workflow

METRICS=("deadline_miss_rate","wrong_preemption_rate","task_thrashing","resume_success_rate","user_override_compliance","completion_rate","wall_clock_s","preemptions","switches")

def one(seed:int,strategy:str):
    h=AffectControlHarness(RuleProvider()); s=AffectiveScheduler(strategy=strategy)
    return TraceRunner(h,s).run(semi_synthetic_workflow(seed))

def run(episodes:int=200,seed:int=41):
    out={}
    for strategy in ("static","edf","urgency","affective"):
        rows=[one(seed+i,strategy) for i in range(episodes)]
        out[strategy]={m:mean_ci95([r[m] for r in rows],bootstrap_samples=1000,seed=seed) for m in METRICS}
    return {"episodes":episodes,"seed":seed,"workload":"semi_synthetic_workflow_v1","warning":"diagnostic semi-synthetic evidence; not external-validity evidence","strategies":out}

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--episodes",type=int,default=200); ap.add_argument("--seed",type=int,default=41); a=ap.parse_args()
    print(json.dumps(run(a.episodes,a.seed),indent=2,sort_keys=True))
