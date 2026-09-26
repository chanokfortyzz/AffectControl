from __future__ import annotations
import argparse, json, random
from affectcontrol import AffectControlHarness, AffectiveScheduler, Event, KeywordRuleBaseline, TaskSpec, reference_policy, StateEngine, ControlPolicy, MemoryControl

def control(h, tid, text, priority="P2", immediate=False):
    return h.process(Event(text, task_id=tid, explicit_user_immediate=immediate), base_priority=priority)["control"]

def one_episode(seed: int, use_affect: bool):
    rng=random.Random(seed); p=reference_policy(warn=False); h=AffectControlHarness(KeywordRuleBaseline(p.rule),state_engine=StateEngine(p.state),control=ControlPolicy(p.control),memory=MemoryControl(p.memory)); s=AffectiveScheduler(p.scheduler,use_affect=use_affect)
    bg=TaskSpec("background", "background work", duration_s=rng.randint(28,38), base_priority="P2", metadata={"expected_interrupt":False})
    s.add_task(bg, control(h,"background","background work","P2"))
    urgent_at=rng.randint(6,16); immediate=(seed%2==0); urgent_duration=rng.randint(3,6)
    noise_at=max(2,urgent_at-rng.randint(2,4)); added_noise=added_urgent=False
    while s.now_s<90 and any(r.status.value not in {"done","failed","cancelled"} for r in s.tasks.values()):
        if not added_noise and s.now_s>=noise_at:
            spec=TaskSpec("noise","not urgent, do this when free",duration_s=4,base_priority="P2",metadata={"expected_interrupt":False})
            s.add_task(spec,control(h,"noise","not urgent, do this when free","P2")); added_noise=True
        if not added_urgent and s.now_s>=urgent_at:
            text="review this right now" if immediate else "urgent deadline, submit today"
            spec=TaskSpec("urgent",text,duration_s=urgent_duration,base_priority="P3",deadline_s=urgent_at+8,metadata={"expected_interrupt":True,"explicit_override":immediate})
            s.add_task(spec,control(h,"urgent",text,"P3",immediate)); added_urgent=True
        s.step()
        if all(r.status.value in {"done","failed","cancelled"} for r in s.tasks.values()) and added_urgent: break
    return s.metrics.summary()

def aggregate(rows):
    keys=rows[0]
    out={}
    for k in keys:
        vals=[r[k] for r in rows if r[k] is not None]
        out[k]=sum(vals)/len(vals) if vals else None
    return out

def run(episodes=100, seed=7):
    return {name:aggregate([one_episode(seed+i,use) for i in range(episodes)]) for name,use in (("static",False),("affective",True))}

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--episodes",type=int,default=100); ap.add_argument("--seed",type=int,default=7); a=ap.parse_args()
    print(json.dumps(run(a.episodes,a.seed),indent=2,sort_keys=True))
