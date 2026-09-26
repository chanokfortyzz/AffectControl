from __future__ import annotations
import warnings
from .profiles import UncalibratedReferenceWarning
import re
from collections.abc import Callable
from typing import Any
from .types import Event,Appraisal
from .config import RuleProviderConfig

class AppraisalError(RuntimeError): pass
class AppraisalTransportError(AppraisalError): pass
class AppraisalResponseError(AppraisalError): pass
class AppraisalMissingFieldError(AppraisalResponseError): pass

class KeywordRuleBaseline:
    """Crude lexical baseline. It is not a dual-process psychological model and is not context complete."""
    IMMEDIATE=("立刻","马上","现在就","immediately","right now","asap")
    URGENT=("紧急","今天要","马上要","deadline","提交","尽快")
    NEGATED=("不急","不用急","别急","不着急","无需马上","不用马上","不需要立刻","no rush","not urgent","not in a hurry","no hurry")
    def __init__(self,config:RuleProviderConfig|None=None):
        if config is None: warnings.warn("KeywordRuleBaseline uses uncalibrated lexical constants",UncalibratedReferenceWarning,stacklevel=2)
        self.config=config or RuleProviderConfig()
    def appraise(self,event:Event,state=None)->Appraisal:
        c=self.config; t=event.text.lower(); negated=any(x in t for x in self.NEGATED)
        immediate=event.explicit_user_immediate or (not negated and any(x in t for x in self.IMMEDIATE))
        urgent=immediate or (not negated and any(x in t for x in self.URGENT))
        punctuation=min(c.punctuation_arousal_cap,c.punctuation_arousal_step*len(re.findall(r"!|！",event.text)))
        return Appraisal(urgency=1.0 if immediate else (c.urgent_urgency if urgent else c.routine_urgency),salience=c.immediate_salience if immediate else (c.urgent_salience if urgent else c.routine_salience),arousal=min(1.0,(c.immediate_arousal if immediate else (c.urgent_arousal if urgent else c.routine_arousal))+punctuation),interest=c.default_interest,tension=c.urgent_tension if urgent else c.routine_tension,certainty=c.default_certainty,competence=c.default_competence,goal_relevance=c.user_goal_relevance if event.kind=="user" else c.nonuser_goal_relevance,goal_activation=c.user_goal_relevance if event.kind=="user" else c.nonuser_goal_relevance,expected_impact=c.urgent_expected_impact if urgent else c.routine_expected_impact,interrupt_value=1.0 if immediate else (c.urgent_interrupt if urgent else c.routine_interrupt),memory_value=c.urgent_memory if urgent else c.routine_memory,reflection_need=c.default_reflection_need,raw={"provider":"keyword_rule_baseline","negated_urgency":negated,"limitations":["lexical","no_scope_parsing","no_multitask_semantics"]}).normalized()

RuleProvider=KeywordRuleBaseline

class MockProvider:
    def __init__(self,appraisal:Appraisal): self.value=appraisal
    def appraise(self,event:Event,state=None)->Appraisal: return self.value

class StructuredAppraisalProvider:
    """Generic transport-injected provider for generative LLMs/classifiers.

    The callable receives a schema-oriented payload and must return a mapping of
    appraisal fields. This is intentionally model/vendor neutral.
    """
    KEYS=("urgency","salience","arousal","interest","tension","goal_activation","certainty","competence","goal_relevance","expected_impact","interrupt_value","memory_value","reflection_need")
    def __init__(self,call:Callable[[dict[str,Any]],Any],*,provider_name:str="structured",missing_policy:str="raise"):
        if missing_policy not in {"raise","neutral","conservative"}: raise ValueError("missing_policy must be raise, neutral, or conservative")
        self.call=call; self.provider_name=provider_name; self.missing_policy=missing_policy
    def _fallback(self,key):
        if self.missing_policy=="neutral": return 0.5
        if self.missing_policy=="conservative": return 1.0 if key in {"urgency","salience","interrupt_value","reflection_need"} else 0.5
        raise AppraisalMissingFieldError(f"missing or invalid appraisal field: {key}")
    def appraise(self,event,state=None)->Appraisal:
        payload={"event":{"text":event.text,"kind":event.kind,"task_id":event.task_id,"goal_id":event.goal_id,"explicit_user_immediate":event.explicit_user_immediate,"explicit_priority":event.explicit_priority,"metadata":event.metadata},"state":state.asdict() if state is not None else None,"required_fields":list(self.KEYS),"scale":[0.0,1.0]}
        try: out=self.call(payload)
        except Exception as exc:
            if self.missing_policy=="raise": raise AppraisalTransportError(f"{self.provider_name} transport failed") from exc
            out={}
        if isinstance(out,Appraisal): return out.normalized()
        if not isinstance(out,dict):
            if self.missing_policy=="raise": raise AppraisalResponseError(f"{self.provider_name} response is not a mapping")
            out={}
        values=out.get("appraisal",out); parsed={}
        for key in self.KEYS:
            value=values.get(key) if isinstance(values,dict) else None
            if isinstance(value,dict): value=value.get("score",value.get("probability",value.get("value")))
            try:
                if value is None: raise ValueError
                parsed[key]=float(value)
            except (TypeError,ValueError): parsed[key]=self._fallback(key)
        parsed["raw"]={"provider":self.provider_name,"response":out,"missing_policy":self.missing_policy}
        return Appraisal(**parsed).normalized()

class JevProvider:
    KEYS=("urgency","salience","arousal","interest","tension","goal_activation","certainty","competence","goal_relevance","expected_impact","interrupt_value","memory_value","reflection_need")
    def __init__(self,call:Callable[[dict[str,Any]],Any],missing_policy:str="raise"):
        if missing_policy not in {"raise","neutral","conservative"}: raise ValueError("missing_policy must be raise, neutral, or conservative")
        self.call=call; self.missing_policy=missing_policy
    def _fallback(self,key):
        if self.missing_policy=="neutral": return 0.5
        if self.missing_policy=="conservative": return 1.0 if key in {"urgency","salience","interrupt_value","reflection_need"} else 0.5
        raise AppraisalMissingFieldError(f"missing or invalid appraisal field: {key}")
    def appraise(self,event,state=None)->Appraisal:
        questions={k:{"type":"noul","instructions":f"Score {k} for this event in the current task/goal context."} for k in self.KEYS}
        payload={"state":{"text":event.text,"kind":event.kind,"explicit_user_immediate":event.explicit_user_immediate,"explicit_priority":event.explicit_priority,"task_id":event.task_id,"goal_id":event.goal_id,"metadata":event.metadata},"questions":questions}
        try: out=self.call(payload)
        except Exception as exc:
            if self.missing_policy=="raise": raise AppraisalTransportError("appraisal transport failed") from exc
            out={}
        if isinstance(out,Appraisal): return out.normalized()
        if not isinstance(out,dict):
            if self.missing_policy=="raise": raise AppraisalResponseError("appraisal response is not a mapping")
            out={}
        answers=out.get("answers",out); vals={}
        for k in self.KEYS:
            v=answers.get(k) if isinstance(answers,dict) else None
            if isinstance(v,dict): v=v.get("noul",v.get("score",v.get("probability",v.get("value"))))
            try:
                if v is None: raise ValueError
                vals[k]=float(v)
            except (TypeError,ValueError): vals[k]=self._fallback(k)
        vals["raw"]={"provider":"jev","response":out,"missing_policy":self.missing_policy}; return Appraisal(**vals).normalized()
