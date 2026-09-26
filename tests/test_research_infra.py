from __future__ import annotations
import json, random, warnings
from affectcontrol import *


def explicit_bundle():
    p=reference_policy(warn=False)
    return p


def test_implicit_reference_parameters_warn():
    with warnings.catch_warnings(record=True) as got:
        warnings.simplefilter("always")
        KeywordRuleBaseline(); StateEngine(); ControlPolicy(); MemoryControl(); AffectiveScheduler()
    assert sum(issubclass(x.category,UncalibratedReferenceWarning) for x in got) >= 5


def test_feature_mask_supports_ablation_without_mutating_state():
    p=explicit_bundle(); state=AffectiveState(urgency=1,salience=.1,arousal=.2,interest=.3,tension=.9,goal_activation=.8)
    appraisal=Appraisal(interrupt_value=1,reflection_need=1)
    all_policy=ControlPolicy(p.control,feature_mask=FeatureMask.all())
    minimal_policy=ControlPolicy(p.control,feature_mask=FeatureMask.minimal())
    a=all_policy.evaluate(Event("x",task_id="x"),state,appraisal)
    b=minimal_policy.evaluate(Event("x",task_id="x"),state,appraisal)
    assert state.salience==.1 and a.drive != b.drive


def test_integrated_runtime_uses_one_simulation_clock():
    p=explicit_bundle(); clock=ManualClock(10)
    h=AffectControlHarness(MockProvider(Appraisal(urgency=.8)),state_engine=StateEngine(p.state,clock=clock),control=ControlPolicy(p.control),memory=MemoryControl(p.memory))
    s=AffectiveScheduler(p.scheduler,clock=clock)
    rt=IntegratedRuntime(h,s,clock)
    rt.submit(TaskSpec("t","task",2,base_priority="P2")); rt.step(1)
    assert h.get_state("t").last_update_s==10
    assert s.now_s==clock.now()==11


def test_sqlite_store_transactions_cleanup_and_schema(tmp_path):
    store=SQLiteStateStore(tmp_path/"state.db")
    for i in range(20): store.save(str(i),AffectiveState(step=i,last_update_s=float(i)))
    assert len(store.load_all())==20
    # updated_at is wall-clock in SQLite store; a far-future cutoff removes all rows deterministically.
    assert store.cleanup(1,now_s=10**12)==20
    assert store.load_all()=={}


def test_logistic_interruption_model_learns_simple_boundary():
    rows=[{"urgency":0.05},{"urgency":0.2},{"urgency":0.8},{"urgency":0.95}]
    model=LogisticInterruptionModel(("urgency",)).fit(rows,[0,0,1,1],epochs=1200,lr=.15)
    assert model.predict_proba({"urgency":.9}) > model.predict_proba({"urgency":.1})


def test_jsonl_trace_loader(tmp_path):
    path=tmp_path/"trace.jsonl"
    path.write_text('\n'.join([json.dumps({"at_s":0,"kind":"arrive","task_id":"a","payload":{"duration_s":2}}),json.dumps({"at_s":1,"kind":"cancel","task_id":"a","payload":{}})]))
    trace=load_jsonl_trace(path)
    assert trace.name=="trace" and len(trace.events)==2 and trace.events[1].kind=="cancel"


def test_trace_sink_audits_explicit_immediate(tmp_path):
    p=explicit_bundle(); sink=JsonlTraceSink(tmp_path/"trace.jsonl")
    h=AffectControlHarness(MockProvider(Appraisal()),state_engine=StateEngine(p.state),control=ControlPolicy(p.control),memory=MemoryControl(p.memory),trace=sink)
    h.process(Event("now",task_id="x",explicit_user_immediate=True))
    rows=[json.loads(x) for x in (tmp_path/"trace.jsonl").read_text().splitlines()]
    assert any(r["event"]=="explicit_user_immediate_override" and r["effective_priority"]=="P0" for r in rows)


def test_jev_error_taxonomy_distinguishes_transport_and_missing():
    def boom(_): raise OSError("offline")
    try: JevProvider(boom).appraise(Event("x",task_id="x"))
    except AppraisalTransportError: pass
    else: raise AssertionError("transport error type expected")
    try: JevProvider(lambda _: {"answers":{}}).appraise(Event("x",task_id="x"))
    except AppraisalMissingFieldError: pass
    else: raise AssertionError("missing-field error type expected")


def test_randomized_state_invariants():
    p=explicit_bundle(); clock=ManualClock(1); engine=StateEngine(p.state,clock=clock)
    state=AffectiveState(last_update_s=clock.now()); rng=random.Random(13)
    for _ in range(1000):
        clock.advance(rng.random()*10)
        a=Appraisal(**{k:rng.uniform(-2,3) for k in ("urgency","salience","arousal","interest","tension","goal_activation","interrupt_value","memory_value","certainty","competence")})
        engine.update(state,a)
        for key in CANDIDATE_STATE_FEATURES:
            assert 0 <= getattr(state,key) <= 1
