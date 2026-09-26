from __future__ import annotations
import multiprocessing as mp
from affectcontrol import *


def test_explicit_immediate_is_hard_override():
    h=AffectControlHarness(MockProvider(Appraisal()),state_engine=StateEngine(StateConfig(alpha=1.0)))
    r=h.process(Event("do it",task_id="a",explicit_user_immediate=True),base_priority="P3")
    assert r["control"].effective_priority=="P0" and r["control"].should_interrupt


def test_task_scopes_do_not_bleed_into_each_other():
    class P:
        def appraise(self,e,state=None):
            return Appraisal(urgency=1,salience=1,tension=1) if e.task_id=="A" else Appraisal()
    h=AffectControlHarness(P(),state_engine=StateEngine(StateConfig(alpha=1.0)))
    a=h.process(Event("high",task_id="A"))["state"]
    b=h.process(Event("low",task_id="B"))["state"]
    assert a.urgency==1 and b.urgency==0 and b.tension==0


def test_unscoped_events_are_transient_not_global():
    class P:
        def appraise(self,e,state=None): return Appraisal(urgency=1 if "high" in e.text else 0)
    h=AffectControlHarness(P(),state_engine=StateEngine(StateConfig(alpha=1.0)))
    h.process(Event("high")); low=h.process(Event("low"))["state"]
    assert low.urgency==0


def test_memory_control_is_the_control_bias_source():
    mem=MemoryControl(MemoryPolicyConfig(reflection_threshold=0.1))
    h=AffectControlHarness(MockProvider(Appraisal(memory_value=1,tension=1,salience=1)),state_engine=StateEngine(StateConfig(alpha=1)),memory=mem)
    r=h.process(Event("task",task_id="x"),relevance=1,recency=1)
    expected=mem.score(r["state"],r["appraisal"],1,1)
    assert r["control"].memory_salience==expected and r["control"].reflection_trigger


def test_rule_provider_handles_negation():
    p=RuleProvider(); a=p.appraise(Event("这个不急，不用马上做",task_id="x"))
    assert a.urgency < .5 and a.interrupt_value < .5 and a.raw["negated_urgency"]


def test_rule_provider_explicit_immediate_beats_negation():
    a=RuleProvider().appraise(Event("不急",task_id="x",explicit_user_immediate=True))
    assert a.urgency==1.0 and a.interrupt_value==1.0


def test_jev_missing_defaults_to_strict_error():
    p=JevProvider(lambda payload:{"answers":{"urgency":{"noul":.9}}})
    try: p.appraise(Event("task",task_id="x"))
    except AppraisalError: pass
    else: raise AssertionError("missing fields must not silently become zero")


def test_jev_neutral_fallback_is_explicit():
    p=JevProvider(lambda payload:{"answers":{"urgency":{"noul":.9}}},missing_policy="neutral")
    a=p.appraise(Event("task",task_id="x"))
    assert a.urgency==.9 and a.salience==.5


def test_decay_reduces_activation():
    s=AffectiveState(arousal=1,salience=1,urgency=1,interest=1,tension=1,last_update_s=100)
    StateEngine(half_life_s=100).decay(s,200)
    assert .49<s.arousal<.51 and .49<s.tension<.51


def test_outcome_reappraisal_is_scoped():
    h=AffectControlHarness(MockProvider(Appraisal(tension=1,urgency=.9)),state_engine=StateEngine(StateConfig(alpha=1)))
    h.process(Event("A",task_id="A")); h.process(Event("B",task_id="B"))
    before_b=h.get_state("B").tension; h.outcome("A",True)
    assert h.get_state("A").tension < 1 and h.get_state("B").tension==before_b


def _writer(path,prefix):
    store=JsonStateStore(path)
    for i in range(40): store.save(f"{prefix}-{i}",AffectiveState(urgency=i/40))


def test_json_store_process_safe_updates(tmp_path):
    path=str(tmp_path/"state.json"); ctx=mp.get_context("spawn")
    a=ctx.Process(target=_writer,args=(path,"A")); b=ctx.Process(target=_writer,args=(path,"B")); a.start(); b.start(); a.join(); b.join()
    rows=JsonStateStore(path).load_all()
    assert a.exitcode==0 and b.exitcode==0 and len(rows)==80


def test_calibration_metrics():
    assert abs(brier_score([0,1],[0,1]))<1e-12
    assert abs(expected_calibration_error([.1,.9],[0,1],bins=2)-.1)<1e-12


def _same_key_incrementer(path,loops):
    store=JsonStateStore(path)
    for _ in range(loops):
        def inc(state):
            state.step += 1
            return state
        store.update("shared",inc)


def test_json_store_same_key_transactions_do_not_lose_updates(tmp_path):
    path=str(tmp_path/"same.json"); ctx=mp.get_context("spawn")
    a=ctx.Process(target=_same_key_incrementer,args=(path,100)); b=ctx.Process(target=_same_key_incrementer,args=(path,100))
    a.start(); b.start(); a.join(); b.join()
    assert a.exitcode==0 and b.exitcode==0 and JsonStateStore(path).load("shared").step==200
