from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Protocol

class Clock(Protocol):
    def now(self) -> float: ...

class SystemClock:
    def now(self) -> float:
        return time.time()

@dataclass(slots=True)
class ManualClock:
    value: float = 0.0
    def now(self) -> float:
        return float(self.value)
    def advance(self, seconds: float) -> float:
        if seconds < 0:
            raise ValueError("clock cannot move backwards")
        self.value += float(seconds)
        return self.value
