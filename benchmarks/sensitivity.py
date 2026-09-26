from __future__ import annotations
import json
from dataclasses import replace
from affectcontrol import AffectControlHarness, ControlPolicy, ControlPolicyConfig, Event, KeywordRuleBaseline, StateConfig, StateEngine, reference_policy

CASES=[
    ("routine work",False),
    ("not urgent, do this when free",False),
    ("urgent deadline, submit today",True),
    ("review this right now",True),
]

def evaluate(cfg):
    tp=fp=tn=fn=0
    for i,(text,label) in enumerate(CASES):
        h=AffectControlHarness(KeywordRuleBaseline(),state_engine=StateEngine(StateConfig(alpha=1.0)),control=ControlPolicy(cfg))
        got=h.process(Event(text,task_id=f"t{i}"),base_priority="P2")["control"].should_interrupt
        if got and label: tp+=1
        elif got and not label: fp+=1
        elif not got and label: fn+=1
        else: tn+=1
    return {"tp":tp,"fp":fp,"tn":tn,"fn":fn,"accuracy":(tp+tn)/len(CASES)}

base=ControlPolicyConfig(); rows=[]
for threshold in (0.55,0.65,0.72,0.80,0.90):
    cfg=replace(base,interrupt_threshold=threshold)
    rows.append({"interrupt_threshold":threshold,**evaluate(cfg)})
print(json.dumps(rows,indent=2))
