from __future__ import annotations
import argparse,json
from affectcontrol import *

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("trace"); ap.add_argument("--strategy",choices=["static","edf","urgency","affective"],default="static"); a=ap.parse_args()
    p=reference_policy(warn=False); trace=load_jsonl_trace(a.trace)
    h=AffectControlHarness(KeywordRuleBaseline(p.rule),state_engine=StateEngine(p.state),control=ControlPolicy(p.control),memory=MemoryControl(p.memory))
    result=TraceRunner(h,AffectiveScheduler(p.scheduler,strategy=a.strategy)).run(trace)
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=="__main__": main()
