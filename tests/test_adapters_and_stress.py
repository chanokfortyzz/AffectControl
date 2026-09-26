from __future__ import annotations
import json, multiprocessing as mp, random
from affectcontrol import *


def _sqlite_increment(path, loops):
    store=SQLiteStateStore(path)
    for _ in range(loops):
        store.update("shared",lambda s: _inc(s))

def _inc(state):
    state.step += 1
    return state


def explicit_harness():
    p=reference_policy(warn=False)
    return AffectControlHarness(MockProvider(Appraisal(urgency=.7,salience=.4,tension=.5)),state_engine=StateEngine(p.state),control=ControlPolicy(p.control),memory=MemoryControl(p.memory))


def test_sqlite_four_process_same_key_contention(tmp_path):
    path=str(tmp_path/"stress.db"); ctx=mp.get_context("spawn")
    procs=[ctx.Process(target=_sqlite_increment,args=(path,200)) for _ in range(4)]
    for p in procs: p.start()
    for p in procs: p.join()
    assert all(p.exitcode==0 for p in procs)
    assert SQLiteStateStore(path).load("shared").step==800


def test_sqlite_thousands_of_keys(tmp_path):
    store=SQLiteStateStore(tmp_path/"many.db")
    for i in range(2000): store.save(f"k-{i}",AffectiveState(step=i))
    rows=store.load_all()
    assert len(rows)==2000 and rows["k-1999"].step==1999


def test_scheduler_randomized_invariants_all_strategies():
    rng=random.Random(91); p=reference_policy(warn=False)
    for strategy in ("static","edf","urgency","learned","affective"):
        s=AffectiveScheduler(p.scheduler,strategy=strategy)
        for i in range(80):
            meta={"urgency_score":rng.random(),"learned_interrupt_score":rng.random(),"learned_interrupt_threshold":.5,"expected_interrupt":bool(rng.getrandbits(1))}
            s.add_task(TaskSpec(str(i),"x",rng.randint(1,8),base_priority=rng.choice(["P1","P2","P3"]),deadline_s=rng.choice([None,rng.randint(5,200)]),metadata=meta),ControlBias(effective_priority=rng.choice(["P1","P2","P3"]),should_interrupt=bool(rng.getrandbits(1)),drive=rng.random()))
        s.run_until_idle(5000)
        assert all(r.remaining_s>=0 for r in s.tasks.values())
        assert all(r.status in {TaskStatus.DONE,TaskStatus.CANCELLED,TaskStatus.FAILED} for r in s.tasks.values())
        assert s.metrics.deadline_misses <= s.metrics.deadline_tasks


def test_langgraph_helper_returns_mergeable_mapping():
    node=LangGraphControlNode(explicit_harness())
    out=node({"input":"do x","task_id":"t","priority":"P2"})
    assert "affectcontrol" in out and out["affectcontrol"]["scope_key"]=="t"


def test_openai_agents_context_helper_mutates_local_context_only():
    ctx=OpenAIAgentsContext(task_id="t")
    out=apply_to_openai_context(explicit_harness(),ctx,"do x")
    assert out is ctx and ctx.affectcontrol["scope_key"]=="t"


def test_autogen_and_crewai_bridges_are_dependency_optional():
    h=explicit_harness()
    assert AutoGenControlBridge(h).before_run("task",task_id="t")["scope_key"]=="t"
    assert CrewAIFlowControlBridge(h).appraise_flow_event("flow",flow_id="g")["scope_key"]=="g"


def test_structured_provider_vendor_neutral():
    keys=StructuredAppraisalProvider.KEYS
    p=StructuredAppraisalProvider(lambda payload:{"appraisal":{k:.6 for k in keys}},provider_name="fixture")
    a=p.appraise(Event("x",task_id="t"))
    assert a.urgency==.6 and a.raw["provider"]=="fixture"


def test_external_trace_rejects_malformed_json(tmp_path):
    p=tmp_path/"bad.jsonl"; p.write_text('{bad}\n')
    try: load_jsonl_trace(p)
    except ValueError as exc: assert "line 1" in str(exc)
    else: raise AssertionError("malformed trace must fail")
