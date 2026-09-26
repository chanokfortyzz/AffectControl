from __future__ import annotations
from dataclasses import dataclass, field
import random
from typing import Any
from .harness import AffectControlHarness
from .scheduler import AffectiveScheduler
from .types import Event, TaskSpec, TaskStatus

@dataclass(slots=True)
class TraceEvent:
    at_s: float
    kind: str
    task_id: str
    payload: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class WorkflowTrace:
    name: str
    events: list[TraceEvent]
    max_runtime_s: float = 600.0

class TraceRunner:
    """Replay task arrivals and environment changes against one scheduler."""
    def __init__(self, harness: AffectControlHarness, scheduler: AffectiveScheduler):
        self.harness=harness; self.scheduler=scheduler; self._outcomes:set[str]=set()
    def _control(self, task_id:str, text:str, priority:str, immediate:bool=False):
        result=self.harness.process(Event(text,task_id=task_id,explicit_user_immediate=immediate),base_priority=priority)
        return result["control"], result["appraisal"]
    def apply(self,event:TraceEvent):
        p=event.payload; s=self.scheduler; tid=event.task_id
        if event.kind=="arrive":
            priority=str(p.get("priority","P2")); text=str(p.get("text",tid)); immediate=bool(p.get("immediate",False))
            control,appraisal=self._control(tid,text,priority,immediate)
            metadata=dict(p.get("metadata") or {}); metadata["urgency_score"]=appraisal.urgency
            metadata.setdefault("explicit_override",immediate); metadata.setdefault("expected_interrupt",bool(p.get("expected_interrupt",immediate)))
            spec=TaskSpec(tid,text,float(p.get("duration_s",10)),priority,s.now_s,p.get("deadline_s"),bool(p.get("preemptible",True)),p.get("goal_id"),metadata)
            s.add_task(spec,control)
        elif event.kind=="revise":
            s.revise_task(tid,duration_delta_s=float(p.get("duration_delta_s",0)),deadline_s=p.get("deadline_s"),base_priority=p.get("priority"))
            if p.get("text") is not None:
                rec=s.tasks[tid]; rec.spec.text=str(p["text"])
                control,appraisal=self._control(tid,rec.spec.text,rec.spec.base_priority,bool(p.get("immediate",False)))
                rec.spec.metadata["urgency_score"]=appraisal.urgency; s.update_control(tid,control)
        elif event.kind=="block": s.block_task(tid)
        elif event.kind=="unblock": s.unblock_task(tid)
        elif event.kind=="cancel": s.cancel_task(tid)
        elif event.kind=="control":
            rec=s.tasks[tid]; text=str(p.get("text",rec.spec.text)); immediate=bool(p.get("immediate",False))
            control,appraisal=self._control(tid,text,rec.spec.base_priority,immediate)
            rec.spec.metadata["urgency_score"]=appraisal.urgency; rec.spec.metadata["explicit_override"] = immediate or rec.spec.metadata.get("explicit_override",False)
            s.update_control(tid,control)
        else: raise ValueError(f"unknown trace event kind: {event.kind}")
    def _collect_outcomes(self):
        for tid,rec in self.scheduler.tasks.items():
            if tid in self._outcomes: continue
            if rec.status==TaskStatus.DONE:
                self.harness.outcome(tid,success=True); self._outcomes.add(tid)
            elif rec.status in {TaskStatus.FAILED,TaskStatus.CANCELLED}:
                self.harness.outcome(tid,success=False); self._outcomes.add(tid)
    def run(self,trace:WorkflowTrace):
        events=sorted(trace.events,key=lambda e:e.at_s); i=0; s=self.scheduler
        while s.now_s<trace.max_runtime_s and (i<len(events) or any(r.status in {TaskStatus.QUEUED,TaskStatus.RUNNING,TaskStatus.PAUSED,TaskStatus.BLOCKED} for r in s.tasks.values())):
            while i<len(events) and events[i].at_s<=s.now_s+1e-9:
                self.apply(events[i]); i+=1
            next_at=events[i].at_s if i<len(events) else None
            dt=s.config.quantum_s
            if next_at is not None and next_at>s.now_s: dt=min(dt,next_at-s.now_s)
            s.step(dt); self._collect_outcomes()
            if i>=len(events) and not any(r.status in {TaskStatus.QUEUED,TaskStatus.RUNNING,TaskStatus.PAUSED} for r in s.tasks.values()): break
        done=sum(r.status==TaskStatus.DONE for r in s.tasks.values()); total=len(s.tasks)
        result=s.metrics.summary(); result.update({"completion_rate":done/total if total else 0.0,"wall_clock_s":s.now_s,"tasks":total})
        return result

def semi_synthetic_workflow(seed:int=0)->WorkflowTrace:
    """Publishable workflow-shaped trace; not a claim of external validity."""
    r=random.Random(seed); urgent_at=r.randint(18,26); immediate=seed%2==0
    events=[
        TraceEvent(0,"arrive","primary",{"text":"prepare a multi-step report","duration_s":48+r.randint(0,8),"priority":"P2","deadline_s":95}),
        TraceEvent(7,"arrive","source-check",{"text":"verify supporting source","duration_s":16,"priority":"P2","deadline_s":70}),
        TraceEvent(11,"block","source-check"),
        TraceEvent(16,"revise","primary",{"text":"report requirement changed; add comparison section","duration_delta_s":12}),
        TraceEvent(20,"unblock","source-check"),
        TraceEvent(urgent_at,"arrive","override",{"text":"review this right now" if immediate else "urgent deadline, submit today","duration_s":7,"priority":"P3","deadline_s":urgent_at+10,"immediate":immediate,"expected_interrupt":True}),
        TraceEvent(34,"arrive","stale-followup",{"text":"low priority stale follow-up","duration_s":9,"priority":"P3","deadline_s":110,"expected_interrupt":False}),
        TraceEvent(39,"cancel","stale-followup"),
        TraceEvent(46,"revise","primary",{"deadline_s":88}),
        TraceEvent(56,"arrive","final-check",{"text":"final consistency check before delivery","duration_s":8,"priority":"P1","deadline_s":92,"expected_interrupt":True}),
    ]
    return WorkflowTrace(f"semi-synthetic-{seed}",events,140)
