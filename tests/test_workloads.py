from affectcontrol import *

def test_trace_runner_handles_revision_block_cancel_and_finishes():
    r=TraceRunner(AffectControlHarness(RuleProvider()),AffectiveScheduler(strategy="affective")).run(semi_synthetic_workflow(2))
    assert r["tasks"]==5 and r["completion_rate"]>=.6 and r["user_override_compliance"]==1.0

def test_edf_is_a_real_scheduler_strategy():
    s=AffectiveScheduler(strategy="edf")
    s.add_task(TaskSpec("late","late",20,deadline_s=100))
    s.step(1)
    s.add_task(TaskSpec("early","early",2,deadline_s=5))
    s.step(1)
    assert s.current_id=="early" and s.metrics.preemptions==1

def test_calibration_threshold_is_fit_without_using_test_labels():
    train_scores=[.1,.2,.8,.9]; labels=[0,0,1,1]
    fit=fit_threshold(train_scores,labels,candidates=[.3,.5,.7])
    assert fit["balanced_accuracy"]==1.0 and .3<=fit["threshold"]<=.7

def test_bootstrap_ci_contains_mean():
    r=mean_ci95([0,1,1,1],bootstrap_samples=300,seed=1)
    assert r["ci95"][0] <= r["mean"] <= r["ci95"][1] and r["n"]==4
