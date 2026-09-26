from __future__ import annotations
import argparse,csv,json,random
from pathlib import Path
from affectcontrol import fit_threshold,threshold_metrics,calibration_report

def load(path):
    rows=list(csv.DictReader(Path(path).open(encoding="utf-8")))
    return [(float(r["score"]),int(r["label"])) for r in rows]

def split(rows,seed=0,train_fraction=.7):
    rows=list(rows); random.Random(seed).shuffle(rows); n=max(1,min(len(rows)-1,int(len(rows)*train_fraction)))
    return rows[:n],rows[n:]

def run(path,seed=0):
    rows=load(path); train,test=split(rows,seed)
    fit=fit_threshold([x for x,_ in train],[y for _,y in train])
    report=threshold_metrics([x for x,_ in test],[y for _,y in test],fit["threshold"])
    return {"fit_on":"train_only","threshold":fit["threshold"],"train":calibration_report([x for x,_ in train],[y for _,y in train]),"test":{**calibration_report([x for x,_ in test],[y for _,y in test]),**report},"n_train":len(train),"n_test":len(test)}

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--seed",type=int,default=0); a=ap.parse_args(); print(json.dumps(run(a.csv,a.seed),indent=2,sort_keys=True))
