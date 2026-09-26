from __future__ import annotations
from .metrics import brier_score, expected_calibration_error

def threshold_metrics(scores,labels,threshold:float):
    pred=[float(s)>=threshold for s in scores]; y=[bool(v) for v in labels]
    tp=sum(a and b for a,b in zip(pred,y)); fp=sum(a and not b for a,b in zip(pred,y)); tn=sum((not a) and (not b) for a,b in zip(pred,y)); fn=sum((not a) and b for a,b in zip(pred,y))
    tpr=tp/(tp+fn) if tp+fn else 0.0; tnr=tn/(tn+fp) if tn+fp else 0.0
    return {"threshold":threshold,"tp":tp,"fp":fp,"tn":tn,"fn":fn,"balanced_accuracy":(tpr+tnr)/2}

def fit_threshold(scores,labels,candidates=None):
    candidates=list(candidates or [i/100 for i in range(5,96,5)])
    rows=[threshold_metrics(scores,labels,t) for t in candidates]
    return max(rows,key=lambda r:(r["balanced_accuracy"],-abs(r["threshold"]-.5)))

def calibration_report(scores,labels,bins:int=10):
    return {"brier":brier_score(scores,labels),"ece":expected_calibration_error(scores,labels,bins),"n":len(list(scores))}
