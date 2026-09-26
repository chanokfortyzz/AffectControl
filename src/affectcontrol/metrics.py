from __future__ import annotations

def brier_score(probabilities, labels):
    p=list(probabilities); y=list(labels)
    if len(p)!=len(y) or not p: raise ValueError("probabilities and labels must be non-empty and equal length")
    return sum((float(a)-float(b))**2 for a,b in zip(p,y))/len(p)

def expected_calibration_error(probabilities, labels, bins:int=10):
    p=list(map(float,probabilities)); y=list(map(float,labels))
    if len(p)!=len(y) or not p: raise ValueError("probabilities and labels must be non-empty and equal length")
    total=len(p); ece=0.0
    for i in range(bins):
        lo=i/bins; hi=(i+1)/bins
        idx=[j for j,v in enumerate(p) if lo<=v<hi or (i==bins-1 and v==1.0)]
        if not idx: continue
        conf=sum(p[j] for j in idx)/len(idx); acc=sum(y[j] for j in idx)/len(idx)
        ece+=len(idx)/total*abs(conf-acc)
    return ece
