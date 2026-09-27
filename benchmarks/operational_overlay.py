from __future__ import annotations
import argparse, json
from pathlib import Path
from affectcontrol import (
    AffectControlHarness, AffectiveScheduler, ControlPolicy, KeywordRuleBaseline,
    MemoryControl, StateEngine, TraceEvent, TraceRunner, WorkflowTrace,
    interrupt_overlay, load_jsonl_trace, mean_ci95, reference_policy,
)

METRICS=("deadline_miss_rate","wrong_preemption_rate","task_thrashing",
         "resume_success_rate","user_override_compliance","completion_rate",
         "wall_clock_s","preemptions","switches")

def make_harness():
    p=reference_policy(warn=False)
    return p,AffectControlHarness(KeywordRuleBaseline(p.rule),
        state_engine=StateEngine(p.state),control=ControlPolicy(p.control),
        memory=MemoryControl(p.memory))

def prepare_trace(path:Path, *, assume_preemptible:bool, mode:str):
    trace=load_jsonl_trace(path,name=path.stem,max_runtime_s=6*3600)
    arrives=[e for e in trace.events if e.kind=="arrive"]
    if not arrives:return None
    if assume_preemptible:
        for e in arrives:e.payload["preemptible"]=True
    first=arrives[0]
    duration=float(first.payload.get("duration_s",10.0))
    at=max(1.0,min(60.0,duration/3.0))
    immediate=(mode=="explicit")
    text="review this right now" if immediate else "urgent deadline, submit today"
    overlay=TraceEvent(at,"arrive",f"overlay-{path.stem}",{
        "text":text,"duration_s":5.0,"priority":"P3","deadline_s":at+8.0,
        "preemptible":True,"immediate":immediate,"expected_interrupt":True,
        "metadata":{"overlay":True,"overlay_mode":mode}
    })
    return interrupt_overlay(trace,[overlay],name=f"{trace.name}+{mode}-overlay")

def run_session(path:Path,strategy:str,*,assume_preemptible:bool,mode:str):
    prepared=prepare_trace(path,assume_preemptible=assume_preemptible,mode=mode)
    if prepared is None:return None
    p,h=make_harness()
    scheduler=AffectiveScheduler(p.scheduler,strategy=strategy)
    return TraceRunner(h,scheduler).run(prepared)

def run(directory,*,mode="explicit",assume_preemptible=False):
    paths=sorted(Path(directory).glob("*.jsonl"))
    strategies=("static","edf","urgency","affective")
    out={}
    for strategy in strategies:
        rows=[run_session(p,strategy,assume_preemptible=assume_preemptible,mode=mode) for p in paths]
        rows=[r for r in rows if r is not None]
        out[strategy]={m:mean_ci95([r[m] for r in rows],bootstrap_samples=2000,seed=17) for m in METRICS}
    return {
      "sessions":len(paths),"overlay_mode":mode,"assume_preemptible":assume_preemptible,
      "warning":"semi-real operational-shape pilot; injected interruption; not external-validity evidence",
      "strategies":out,
    }
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("directory")
    ap.add_argument("--overlay-mode",choices=["explicit","inferred"],default="explicit")
    ap.add_argument("--assume-preemptible",action="store_true")
    args=ap.parse_args()
    print(json.dumps(run(args.directory,mode=args.overlay_mode,
                         assume_preemptible=args.assume_preemptible),
                     indent=2,sort_keys=True))

if __name__=="__main__":main()
