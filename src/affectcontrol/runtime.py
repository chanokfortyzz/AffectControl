from __future__ import annotations
from .clock import ManualClock
from .types import Event,TaskSpec,TaskStatus

class IntegratedRuntime:
    """Owns appraisal/state/control/scheduling so callers do not manually synchronize ControlBias."""
    def __init__(self,harness,scheduler,clock:ManualClock|None=None):
        self.harness=harness; self.scheduler=scheduler; self.clock=clock or ManualClock(float(getattr(scheduler,'now_s',0.0)))
        self.harness.state_engine.clock=self.clock; self.scheduler.clock=self.clock; self.scheduler.now_s=self.clock.now()
    def submit(self,spec:TaskSpec,*,immediate:bool=False):
        event=Event(spec.text,task_id=spec.task_id,goal_id=spec.goal_id,explicit_user_immediate=immediate)
        result=self.harness.process(event,base_priority=spec.base_priority,now_s=self.clock.now())
        spec.created_at_s=self.clock.now(); spec.metadata.setdefault('urgency_score',result['appraisal'].urgency); spec.metadata.setdefault('explicit_override',immediate)
        self.scheduler.add_task(spec,result['control']); return result
    def event(self,task_id:str,text:str,*,immediate:bool=False):
        rec=self.scheduler.tasks[task_id]; result=self.harness.process(Event(text,task_id=task_id,goal_id=rec.spec.goal_id,explicit_user_immediate=immediate),base_priority=rec.spec.base_priority,now_s=self.clock.now())
        rec.spec.text=text; rec.spec.metadata['urgency_score']=result['appraisal'].urgency; self.scheduler.update_control(task_id,result['control']); return result
    def step(self,dt:float|None=None):
        before={k:v.status for k,v in self.scheduler.tasks.items()}; out=self.scheduler.step(dt)
        for tid,rec in self.scheduler.tasks.items():
            if before.get(tid)!=TaskStatus.DONE and rec.status==TaskStatus.DONE:
                self.harness.outcome(tid,True,now_s=self.clock.now())
        return out
    def run_until_idle(self,max_s:float=100000):
        end=self.clock.now()+max_s
        while self.clock.now()<end and any(r.status in {TaskStatus.QUEUED,TaskStatus.PAUSED,TaskStatus.RUNNING} for r in self.scheduler.tasks.values()): self.step()
        return self.scheduler.metrics.summary()
