from __future__ import annotations
import importlib.util, json
from pathlib import Path
from affectcontrol import roc_auc_score

MODULE_PATH=Path(__file__).resolve().parents[1]/'benchmarks'/'appraisal_compare.py'
spec=importlib.util.spec_from_file_location('appraisal_compare',MODULE_PATH)
mod=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)

def test_roc_auc_dependency_free():
    assert roc_auc_score([0.9,0.8,0.2,0.1],[1,1,0,0])==1.0
    assert roc_auc_score([0.5,0.5],[1,0])==0.5

def test_appraisal_compare_reports_common_provider_metrics(tmp_path):
    rows=[
      {'id':'1','label':1,'predictions':{'a':.9,'b':.6},'latency_ms':{'a':10,'b':100}},
      {'id':'2','label':0,'predictions':{'a':.1,'b':.4},'latency_ms':{'a':12,'b':110}},
      {'id':'3','label':1,'predictions':{'a':.8,'b':.55},'latency_ms':{'a':11,'b':90}},
      {'id':'4','label':0,'predictions':{'a':.2,'b':.45},'latency_ms':{'a':9,'b':95}},
    ]
    path=tmp_path/'predictions.jsonl'
    path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
    out=mod.compare(path,.5)
    assert out['providers']['a']['auroc']==1.0
    assert out['providers']['a']['brier'] < out['providers']['b']['brier']
    pair=out['paired_brier']['a__vs__b']
    assert pair['n']==4 and pair['delta_brier_a_minus_b']<0
