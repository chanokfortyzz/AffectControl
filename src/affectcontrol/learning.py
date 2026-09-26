from __future__ import annotations
import math
from dataclasses import dataclass, field

def _sigmoid(x: float) -> float:
    if x >= 0:
        z=math.exp(-x); return 1/(1+z)
    z=math.exp(x); return z/(1+z)

@dataclass(slots=True)
class LogisticInterruptionModel:
    feature_names: tuple[str,...]
    weights: dict[str,float]=field(default_factory=dict)
    bias: float=0.0
    fitted: bool=False
    def fit(self, rows, labels, *, epochs: int=800, lr: float=0.08, l2: float=1e-3):
        rows=list(rows); labels=list(labels)
        if len(rows)!=len(labels) or not rows:
            raise ValueError("rows and labels must be non-empty and equal length")
        w={name:0.0 for name in self.feature_names}; b=0.0; n=len(rows)
        for _ in range(epochs):
            gw={name:0.0 for name in self.feature_names}; gb=0.0
            for row,y in zip(rows,labels):
                p=_sigmoid(b+sum(w[k]*float(row.get(k,0.0)) for k in self.feature_names)); e=p-float(y)
                gb+=e
                for k in self.feature_names: gw[k]+=e*float(row.get(k,0.0))
            b-=lr*gb/n
            for k in w: w[k]-=lr*((gw[k]/n)+l2*w[k])
        self.weights=w; self.bias=b; self.fitted=True; return self
    def predict_proba(self,row) -> float:
        if not self.fitted: raise RuntimeError("model is not fitted")
        return _sigmoid(self.bias+sum(self.weights[k]*float(row.get(k,0.0)) for k in self.feature_names))
