from __future__ import annotations
import math, random

def mean_ci95(values,*,bootstrap_samples:int=2000,seed:int=0):
    xs=[float(x) for x in values if x is not None]
    if not xs: return {"mean":None,"ci95":[None,None],"n":0}
    mean=sum(xs)/len(xs)
    if len(xs)==1: return {"mean":mean,"ci95":[mean,mean],"n":1}
    rng=random.Random(seed); means=[]
    for _ in range(bootstrap_samples): means.append(sum(rng.choice(xs) for _ in xs)/len(xs))
    means.sort(); lo=means[int(.025*(len(means)-1))]; hi=means[int(.975*(len(means)-1))]
    return {"mean":mean,"ci95":[lo,hi],"n":len(xs)}
