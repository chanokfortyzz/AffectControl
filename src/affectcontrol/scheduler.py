from __future__ import annotations
import warnings
from .profiles import UncalibratedReferenceWarning
from dataclasses import dataclass, field
from statistics import mean
from .config import SchedulerConfig
from .clock import ManualClock
from .global_context import GlobalControlContext
from .control import RANK
from .types import ControlBias, TaskRecord, TaskSpec, TaskStatus, clamp

@dataclass(slots=True)
class SchedulerMetrics:
    preemption_latencies_s: list[float]=field(default_factory=list)
    deadline_tasks: int=0
    deadline_misses: int=0
    preemptions: int=0
    wrong_preemptions: int=0
    switches: int=0
    thrashes: int=0
    resume_attempts: int=0
    resume_successes: int=0
    override_tasks: int=0
    override_complied: int=0
    def summary(self):
        return {
            "mean_preemption_latency_s": mean(self.preemption_latencies_s) if self.preemption_latencies_s else None,
            "deadline_miss_rate": self.deadline_misses/self.deadline_tasks if self.deadline_tasks else 0.0,
            "wrong_preemption_rate": self.wrong_preemptions/self.preemptions if self.preemptions else 0.0,
            "task_thrashing": self.thrashes,
            "resume_success_rate": self.resume_successes/self.resume_attempts if self.resume_attempts else None,
            "user_override_compliance": self.override_complied/self.override_tasks if self.override_tasks else None,
            "preemptions": self.preemptions,
            "switches": self.switches,
        }

class AffectiveScheduler:
    """Small deterministic lifecycle scheduler for experiments and adapters."""
    def __init__(self, config: SchedulerConfig|None=None, *, strategy: str="affective", use_affect: bool|None=None, clock=None, global_context: GlobalControlContext|None=None):
        if use_affect is not None:
            strategy="affective" if use_affect else "static"
        if strategy not in {"affective","static","edf","urgency","learned"}:
            raise ValueError("strategy must be affective, static, edf, urgency, or learned")
        if config is None: warnings.warn("AffectiveScheduler is using uncalibrated reference scheduler parameters",UncalibratedReferenceWarning,stacklevel=2)
        self.config=config or SchedulerConfig(); self.strategy=strategy
        self.use_affect=(strategy=="affective"); self.clock=clock or ManualClock(0.0); self.global_context=global_context or GlobalControlContext()
        self.tasks: dict[str,TaskRecord]={}; self.current_id: str|None=None; self.now_s=float(self.clock.now())
        self.metrics=SchedulerMetrics(); self._missed:set[str]=set(); self._preempt_times:list[float]=[]; self._override_complied:set[str]=set()
    def add_task(self,spec:TaskSpec,control:ControlBias|None=None):
        if spec.task_id in self.tasks: raise ValueError(f"duplicate task_id: {spec.task_id}")
        rec=TaskRecord(spec=spec,control=control or ControlBias(effective_priority=spec.base_priority))
        if rec.control.should_interrupt: rec.interrupt_requested_at_s=self.now_s
        if bool(spec.metadata.get("explicit_override")):
            self.metrics.override_tasks+=1; spec.metadata["_override_arrived_while_busy"]=bool(self.current_id)
        self.tasks[spec.task_id]=rec
        if spec.deadline_s is not None: self.metrics.deadline_tasks+=1
        return rec
    def revise_task(self,task_id:str,*,duration_delta_s:float=0.0,deadline_s:float|None=None,base_priority:str|None=None):
        rec=self.tasks[task_id]
        if rec.status in {TaskStatus.DONE,TaskStatus.FAILED,TaskStatus.CANCELLED}: return rec
        if duration_delta_s:
            rec.remaining_s=max(0.0,rec.remaining_s+float(duration_delta_s))
        if deadline_s is not None: rec.spec.deadline_s=float(deadline_s)
        if base_priority is not None: rec.spec.base_priority=base_priority
        return rec
    def block_task(self,task_id:str):
        rec=self.tasks[task_id]
        if rec.status==TaskStatus.RUNNING: self.current_id=None
        if rec.status not in {TaskStatus.DONE,TaskStatus.FAILED,TaskStatus.CANCELLED}: rec.status=TaskStatus.BLOCKED
        return rec
    def unblock_task(self,task_id:str):
        rec=self.tasks[task_id]
        if rec.status==TaskStatus.BLOCKED: rec.status=TaskStatus.QUEUED
        return rec
    def cancel_task(self,task_id:str):
        rec=self.tasks[task_id]
        if self.current_id==task_id: self.current_id=None
        if rec.status not in {TaskStatus.DONE,TaskStatus.FAILED}: rec.status=TaskStatus.CANCELLED
        return rec
    def update_control(self,task_id:str,control:ControlBias):
        rec=self.tasks[task_id]; rec.control=control
        if control.should_interrupt and rec.interrupt_requested_at_s is None: rec.interrupt_requested_at_s=self.now_s
    def _deadline_pressure(self,rec:TaskRecord):
        d=rec.spec.deadline_s
        if d is None: return 0.0
        slack=d-self.now_s-rec.remaining_s
        if slack<=0: return 1.0
        return clamp(1.0-slack/max(self.config.deadline_horizon_s,1e-9))
    def _priority_value(self, rec:TaskRecord):
        p=rec.control.effective_priority if self.strategy=="affective" else rec.spec.base_priority
        return (3-RANK.get(p,2))/3.0
    def _global_adjust(self,rec:TaskRecord,score:float)->float:
        score += self.global_context.task_adjustment(rec.spec.goal_id)
        if self.current_id and rec.spec.task_id != self.current_id:
            score -= clamp(self.global_context.resource_pressure)*self.config.switch_penalty
        return score
    def _score(self,rec:TaskRecord):
        priority=self._priority_value(rec)
        if self.strategy=="static":
            return self._global_adjust(rec,priority)
        if self.strategy=="edf":
            if rec.spec.deadline_s is None:
                return self._global_adjust(rec,0.05*priority)
            ttd=max(0.0,rec.spec.deadline_s-self.now_s)
            edf=1.0/(1.0+ttd/max(self.config.deadline_horizon_s,1e-9))
            return self._global_adjust(rec,edf+0.05*priority)
        if self.strategy=="urgency":
            urgency=clamp(rec.spec.metadata.get("urgency_score",0.0))
            return self._global_adjust(rec,0.85*urgency+0.15*priority)
        if self.strategy=="learned":
            learned=clamp(rec.spec.metadata.get("learned_interrupt_score",0.0))
            return self._global_adjust(rec,0.85*learned+0.15*priority)
        affect=rec.control.drive
        score=self.config.priority_weight*priority+self.config.affect_weight*affect+self.config.deadline_weight*self._deadline_pressure(rec)
        if self.current_id and rec.spec.task_id!=self.current_id: score-=self.config.switch_penalty
        return self._global_adjust(rec,score)
    def _should_preempt(self,best:TaskRecord,current:TaskRecord):
        if not current.spec.preemptible or best.spec.task_id==current.spec.task_id:
            return False
        if self.strategy=="static":
            return RANK.get(best.spec.base_priority,2) < RANK.get(current.spec.base_priority,2)
        if self.strategy=="edf":
            bd,cd=best.spec.deadline_s,current.spec.deadline_s
            return bd is not None and (cd is None or bd < cd)
        if self.strategy=="urgency":
            return clamp(best.spec.metadata.get("urgency_score",0.0)) >= 0.75 and self._score(best)>self._score(current)
        if self.strategy=="learned":
            return clamp(best.spec.metadata.get("learned_interrupt_score",0.0)) >= float(best.spec.metadata.get("learned_interrupt_threshold",0.5)) and self._score(best)>self._score(current)
        margin=self._score(best)-self._score(current)
        return best.control.should_interrupt and margin>=self.config.preempt_margin
    def _eligible(self): return [r for r in self.tasks.values() if r.status in {TaskStatus.QUEUED,TaskStatus.PAUSED}]
    def _best(self):
        rows=self._eligible()
        return max(rows,key=lambda r:(self._score(r),-r.spec.created_at_s,r.spec.task_id)) if rows else None
    def _switch_to(self,rec:TaskRecord,preempt:bool=False):
        old=self.tasks.get(self.current_id) if self.current_id else None
        if old and old.spec.task_id!=rec.spec.task_id and old.status==TaskStatus.RUNNING:
            old.status=TaskStatus.PAUSED; old.paused_at_s=self.now_s
        if self.current_id!=rec.spec.task_id:
            self.metrics.switches+=1
        if bool(rec.spec.metadata.get("explicit_override")) and rec.spec.task_id not in self._override_complied:
            if preempt or not bool(rec.spec.metadata.get("_override_arrived_while_busy")):
                self._override_complied.add(rec.spec.task_id); self.metrics.override_complied+=1
        if preempt:
            self.metrics.preemptions+=1; self._preempt_times.append(self.now_s)
            recent=[t for t in self._preempt_times if self.now_s-t<=self.config.thrash_window_s]
            if len(recent)>=self.config.thrash_preemptions: self.metrics.thrashes+=1
            if not bool(rec.spec.metadata.get("expected_interrupt",True)): self.metrics.wrong_preemptions+=1
            if rec.interrupt_requested_at_s is not None:
                self.metrics.preemption_latencies_s.append(max(0.0,self.now_s-rec.interrupt_requested_at_s))
        if rec.status==TaskStatus.PAUSED:
            rec.resume_count+=1; self.metrics.resume_attempts+=1
        rec.status=TaskStatus.RUNNING
        if rec.started_at_s is None: rec.started_at_s=self.now_s
        self.current_id=rec.spec.task_id
    def _check_deadlines(self):
        for tid,r in self.tasks.items():
            if r.spec.deadline_s is None or tid in self._missed or self.now_s<=r.spec.deadline_s:
                continue
            late_done = r.status==TaskStatus.DONE and (r.completed_at_s or self.now_s)>r.spec.deadline_s
            if r.status!=TaskStatus.DONE or late_done:
                self._missed.add(tid); self.metrics.deadline_misses+=1
    def step(self,dt:float|None=None):
        dt=self.config.quantum_s if dt is None else dt; current=self.tasks.get(self.current_id) if self.current_id else None
        best=self._best()
        if current is None or current.status!=TaskStatus.RUNNING:
            if best: self._switch_to(best)
        elif best and self._should_preempt(best,current):
            self._switch_to(best,preempt=True); current=self.tasks[self.current_id]
        current=self.tasks.get(self.current_id) if self.current_id else None
        if current and current.status==TaskStatus.RUNNING:
            current.remaining_s=max(0.0,current.remaining_s-dt); self.clock.advance(dt); self.now_s=float(self.clock.now())
            if current.remaining_s<=0:
                current.status=TaskStatus.DONE; current.completed_at_s=self.now_s
                if current.resume_count>0: self.metrics.resume_successes+=1
                self.current_id=None
        else: self.clock.advance(dt); self.now_s=float(self.clock.now())
        self._check_deadlines(); return current
    def run_until_idle(self,max_s:float=100000):
        end=self.now_s+max_s
        while self.now_s<end and any(r.status in {TaskStatus.QUEUED,TaskStatus.PAUSED,TaskStatus.RUNNING} for r in self.tasks.values()): self.step()
        return self.metrics.summary()
