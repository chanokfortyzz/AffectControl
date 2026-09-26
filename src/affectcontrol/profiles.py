from __future__ import annotations
import warnings
from dataclasses import dataclass
from .config import RuleProviderConfig, StateConfig, MemoryPolicyConfig, ControlPolicyConfig, SchedulerConfig

class UncalibratedReferenceWarning(UserWarning):
    pass

@dataclass(frozen=True, slots=True)
class ReferencePolicyBundle:
    rule: RuleProviderConfig
    state: StateConfig
    memory: MemoryPolicyConfig
    control: ControlPolicyConfig
    scheduler: SchedulerConfig
    status: str = "uncalibrated_reference"

def reference_policy(*, warn: bool = True) -> ReferencePolicyBundle:
    if warn:
        warnings.warn(
            "AffectControl reference parameters are uncalibrated and are not production or scientific defaults.",
            UncalibratedReferenceWarning, stacklevel=2,
        )
    return ReferencePolicyBundle(
        RuleProviderConfig(), StateConfig(), MemoryPolicyConfig(), ControlPolicyConfig(), SchedulerConfig()
    )
