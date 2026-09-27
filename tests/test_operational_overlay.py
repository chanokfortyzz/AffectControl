from __future__ import annotations
import importlib.util, json
from pathlib import Path

MODULE_PATH=Path(__file__).resolve().parents[1]/"benchmarks"/"operational_overlay.py"
spec=importlib.util.spec_from_file_location("operational_overlay",MODULE_PATH)
mod=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)

def write_session(path:Path,duration:float):
    row={"at_s":0.0,"kind":"arrive","task_id":path.stem,
         "payload":{"text":"operational task","duration_s":duration,
                    "priority":"P2","preemptible":False,
                    "immediate":False,"expected_interrupt":False,
                    "metadata":{"duration_source":"test-proxy"}}}
    path.write_text(json.dumps(row)+"\n",encoding="utf-8")

def test_operational_overlay_is_explicit_about_counterfactual_preemptibility(tmp_path):
    write_session(tmp_path/"session-001.jsonl",30)
    trace=mod.prepare_trace(tmp_path/"session-001.jsonl",
                            assume_preemptible=True,mode="explicit")
    assert trace is not None
    original=[e for e in trace.events if not e.task_id.startswith("overlay-")][0]
    overlay=[e for e in trace.events if e.task_id.startswith("overlay-")][0]
    assert original.payload["preemptible"] is True
    assert overlay.payload["metadata"]["overlay"] is True
    assert overlay.payload["immediate"] is True

def test_operational_overlay_runner_reports_all_reference_strategies(tmp_path):
    write_session(tmp_path/"session-001.jsonl",30)
    write_session(tmp_path/"session-002.jsonl",18)
    result=mod.run(tmp_path,mode="explicit",assume_preemptible=True)
    assert result["sessions"]==2
    assert result["assume_preemptible"] is True
    assert set(result["strategies"])=={"static","edf","urgency","affective"}
    assert "not external-validity evidence" in result["warning"]
    for metrics in result["strategies"].values():
        assert metrics["deadline_miss_rate"]["n"]==2
