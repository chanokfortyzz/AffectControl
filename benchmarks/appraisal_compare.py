from __future__ import annotations
import argparse, json, math, random
from pathlib import Path
from affectcontrol import brier_score, expected_calibration_error, roc_auc_score, threshold_metrics

def percentile(xs,q):
    if not xs:return None
    ys=sorted(float(x) for x in xs)
    i=min(len(ys)-1,max(0,round((len(ys)-1)*q)))
    return ys[i]

def provider_report(rows,provider,threshold):
    usable=[r for r in rows if provider in (r.get('predictions') or {})]
    scores=[float(r['predictions'][provider]) for r in usable]
    labels=[int(r['label']) for r in usable]
    lat=[float((r.get('latency_ms') or {}).get(provider)) for r in usable if (r.get('latency_ms') or {}).get(provider) is not None]
    cost=[float((r.get('cost_usd') or {}).get(provider)) for r in usable if (r.get('cost_usd') or {}).get(provider) is not None]
    return {
      'n':len(usable),'coverage':len(usable)/len(rows) if rows else 0.0,
      'brier':brier_score(scores,labels) if usable else None,
      'ece':expected_calibration_error(scores,labels) if usable else None,
      'auroc':roc_auc_score(scores,labels) if usable else None,
      'threshold_metrics':threshold_metrics(scores,labels,threshold) if usable else None,
      'mean_latency_ms':sum(lat)/len(lat) if lat else None,
      'p95_latency_ms':percentile(lat,.95),'mean_cost_usd':sum(cost)/len(cost) if cost else None,
    }
def paired_brier_bootstrap(rows,a,b,samples=2000,seed=17):
    common=[r for r in rows if a in (r.get('predictions') or {}) and b in (r.get('predictions') or {})]
    if not common:return {'n':0,'delta_brier_a_minus_b':None,'ci95':[None,None]}
    diffs=[]
    for r in common:
        y=float(r['label']);pa=float(r['predictions'][a]);pb=float(r['predictions'][b])
        diffs.append((pa-y)**2-(pb-y)**2)
    point=sum(diffs)/len(diffs)
    rng=random.Random(seed);boots=[]
    for _ in range(samples):
        boots.append(sum(rng.choice(diffs) for _ in diffs)/len(diffs))
    boots.sort();lo=boots[int(.025*(len(boots)-1))];hi=boots[int(.975*(len(boots)-1))]
    return {'n':len(common),'delta_brier_a_minus_b':point,'ci95':[lo,hi]}

def load_rows(path):
    rows=[]
    for n,line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(),1):
        if not line.strip():continue
        row=json.loads(line)
        if int(row['label']) not in (0,1):raise ValueError(f'line {n}: label must be 0/1')
        preds=row.get('predictions') or {}
        for name,v in preds.items():
            x=float(v)
            if not 0<=x<=1:raise ValueError(f'line {n}: prediction {name} outside [0,1]')
        rows.append(row)
    if not rows:raise ValueError('empty dataset')
    return rows

def compare(path,threshold=.5):
    rows=load_rows(path)
    providers=sorted({p for r in rows for p in (r.get('predictions') or {})})
    reports={p:provider_report(rows,p,threshold) for p in providers}
    pairs={}
    for i,a in enumerate(providers):
        for b in providers[i+1:]:pairs[f'{a}__vs__{b}']=paired_brier_bootstrap(rows,a,b)
    return {'n_rows':len(rows),'threshold':threshold,'providers':reports,'paired_brier':pairs,
            'warning':'evaluation only; labels and provider predictions must be frozen before final reporting'}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dataset')
    ap.add_argument('--threshold',type=float,default=.5)
    args=ap.parse_args()
    print(json.dumps(compare(args.dataset,args.threshold),indent=2,sort_keys=True))

if __name__=='__main__':main()
