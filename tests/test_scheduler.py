from affectcontrol import *


def immediate_control(tid):
    h=AffectControlHarness(RuleProvider(),state_engine=StateEngine(StateConfig(alpha=1.0)))
    return h.process(Event("do it right now",task_id=tid,explicit_user_immediate=True),base_priority="P3")["control"]


def test_scheduler_preempts_and_resumes():
    s=AffectiveScheduler()
    bg=TaskSpec("bg","background",20,base_priority="P2",metadata={"expected_interrupt":False})
    s.add_task(bg,ControlBias(effective_priority="P2")); s.step(); s.step()
    urgent=TaskSpec("u","urgent",2,base_priority="P3",deadline_s=8,metadata={"expected_interrupt":True})
    s.add_task(urgent,immediate_control("u")); s.step()
    assert s.tasks["bg"].status==TaskStatus.PAUSED and s.tasks["u"].status==TaskStatus.RUNNING
    s.run_until_idle()
    assert s.tasks["bg"].status==TaskStatus.DONE and s.tasks["u"].status==TaskStatus.DONE
    m=s.metrics.summary(); assert m["preemptions"]==1 and m["resume_success_rate"]==1.0


def test_static_scheduler_can_miss_urgent_deadline_without_preemption():
    s=AffectiveScheduler(use_affect=False)
    s.add_task(TaskSpec("bg","background",20,base_priority="P2"),ControlBias(effective_priority="P2")); s.step()
    s.add_task(TaskSpec("u","urgent",2,base_priority="P3",deadline_s=5),immediate_control("u")); s.run_until_idle()
    assert s.metrics.deadline_misses==1


def test_wrong_preemption_is_measured_against_scenario_label():
    s=AffectiveScheduler(); s.add_task(TaskSpec("bg","bg",10),ControlBias(effective_priority="P2")); s.step()
    bad=TaskSpec("bad","noise",1,base_priority="P3",metadata={"expected_interrupt":False})
    s.add_task(bad,ControlBias(effective_priority="P0",should_interrupt=True,drive=1,interrupt_score=1)); s.step()
    assert s.metrics.wrong_preemptions==1


def test_deadline_pressure_is_part_of_queue_order():
    s=AffectiveScheduler(use_affect=False)
    s.add_task(TaskSpec("late","late",2,base_priority="P2",deadline_s=100),ControlBias(effective_priority="P2"))
    s.add_task(TaskSpec("soon","soon",2,base_priority="P2",deadline_s=3),ControlBias(effective_priority="P2"))
    s.step(); assert s.tasks["soon"].status==TaskStatus.RUNNING


def test_explicit_override_compliance_requires_actual_preemption_when_busy():
    a=AffectiveScheduler(); a.add_task(TaskSpec("bg","bg",10),ControlBias(effective_priority="P2")); a.step()
    a.add_task(TaskSpec("u","u",1,base_priority="P3",metadata={"expected_interrupt":True,"explicit_override":True}),immediate_control("u")); a.step()
    assert a.metrics.summary()["user_override_compliance"]==1.0
    b=AffectiveScheduler(use_affect=False); b.add_task(TaskSpec("bg","bg",10),ControlBias(effective_priority="P2")); b.step()
    b.add_task(TaskSpec("u","u",1,base_priority="P3",metadata={"expected_interrupt":True,"explicit_override":True}),immediate_control("u")); b.run_until_idle()
    assert b.metrics.summary()["user_override_compliance"]==0.0
