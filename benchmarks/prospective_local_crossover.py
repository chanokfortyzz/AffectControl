"""Exploratory local-subprocess crossover: never report as E2 evidence.

Freeze tasks, assigned deadlines, reference model and randomized arm order
BEFORE observing outputs. Actually execute pytest in child processes, not
simulated scheduler ticks. No live Agent preemption or natural user deadline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import time

from affectcontrol import (
    AffectControlHarness, AffectiveScheduler, ControlPolicy, Event,
    KeywordRuleBaseline, MemoryControl, StateEngine, TaskSpec,
    reference_policy,
)
from benchmarks.capture_execution import _write_exclusive, capture

PROTOCOL = "isolated-real-subprocess-balanced-crossover-v2"
TASKS = (
    dict(task_id="core", test_file="tests/test_core.py", priority="P2",
         message="prepare a routine validation report", deadline_s=2.0),
    dict(task_id="scheduler", test_file="tests/test_scheduler.py", priority="P3",
         message="critical urgent review, do this right now", deadline_s=1.0),
    dict(task_id="workloads", test_file="tests/test_workloads.py", priority="P1",
         message="scheduled verification of task workloads", deadline_s=2.6),
    dict(task_id="trace", test_file="tests/test_trace_cohort.py", priority="P0",
         message="routine data quality check", deadline_s=3.6),
)
ARMS = ("affective", "urgency")


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")) + "\n").encode()


def freeze_plan(pairs=2, seed=20261108, tasks=TASKS):
    if type(pairs) is not int or pairs not in (2, 4, 6):
        raise ValueError("pairs must be even integer 2, 4, or 6 for AB/BA balance")
    if type(seed) is not int:
        raise ValueError("seed must be integer")
    if not 2 <= len(tasks) <= 8:
        raise ValueError("need 2..8 competing tasks")
    seen = set()
    checked = []
    allowed = {x["test_file"] for x in TASKS}
    for task in tasks:
        if set(task) != {"task_id", "test_file", "priority", "message", "deadline_s"}:
            raise ValueError("invalid task schema")
        tid = task["task_id"]
        if not isinstance(tid, str) or not tid.isidentifier() or tid in seen:
            raise ValueError("duplicate or invalid task id")
        seen.add(tid)
        if task["test_file"] not in allowed:
            raise ValueError("task command not in approved allowlist")
        if task["priority"] not in ("P0", "P1", "P2", "P3"):
            raise ValueError("invalid priority")
        if not isinstance(task["message"], str) or not task["message"]:
            raise ValueError("empty task description")
        deadline = task["deadline_s"]
        if type(deadline) not in (int, float) or not math.isfinite(deadline) or deadline <= 0:
            raise ValueError("assigned deadline must be finite positive")
        checked.append(dict(task))
    rng = random.Random(seed)
    first = list(ARMS)
    rng.shuffle(first)
    orders = [list(first) if i % 2 == 0 else list(reversed(first))
              for i in range(pairs)]
    return {
        "protocol": PROTOCOL, "pairs": pairs, "seed": seed,
        "tasks": checked, "arm_orders": orders,
        "primary_descriptive_endpoint":
            "local_pytest_exit_zero_before_experimentally_assigned_deadline",
        "deadline_source": "experimental_assignment_not_observed_user_deadline",
        "status": "exploratory_E1_post_pilot_balance_amendment",
        "amendment": ("AB/BA alternation added AFTER inspecting the original "
                      "unbalanced negative exploratory result; not a new "
                      "independent confirmatory study."),
    }


def choose(tasks, strategy, elapsed):
    if strategy not in ARMS or not tasks:
        raise ValueError("bad strategy or empty queue")
    policy = reference_policy(warn=False)
    harness = AffectControlHarness(
        KeywordRuleBaseline(policy.rule),
        state_engine=StateEngine(policy.state),
        control=ControlPolicy(policy.control),
        memory=MemoryControl(policy.memory),
    )
    scheduler = AffectiveScheduler(policy.scheduler, strategy=strategy)
    scheduler.now_s = elapsed
    scores = {}
    for task in tasks:
        tid = task["task_id"]
        result = harness.process(
            Event(task["message"], task_id=tid),
            base_priority=task["priority"], now_s=elapsed,
        )
        spec = TaskSpec(
            tid, task["message"], 1.0, task["priority"], 0.0,
            task["deadline_s"], True, None,
            {"urgency_score": result["appraisal"].urgency},
        )
        scheduler.add_task(spec, result["control"])
        scores[tid] = float(scheduler._score(scheduler.tasks[tid]))
    selected = min(tasks, key=lambda task: (-scores[task["task_id"]], task["task_id"]))
    return selected, scores


def run(repo, root, *, pairs=2, seed=20261108, tasks=TASKS, runner=None):
    repo = Path(repo).resolve()
    if not (repo / "pyproject.toml").is_file():
        raise ValueError("missing research project")
    plan = freeze_plan(pairs, seed, tasks)
    for task in plan["tasks"]:
        if not (repo / task["test_file"]).is_file():
            raise ValueError("approved test file missing")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    plan["source_git_sha"] = head
    plan["runner_script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    root = Path(root)
    if root.exists():
        raise FileExistsError("experiment root exists; no rerun/overwrite")
    root.mkdir(parents=True, exist_ok=False)
    frozen_bytes = canonical(plan)
    _write_exclusive(root / "frozen-plan.json", frozen_bytes)
    plan_hash = hashlib.sha256(frozen_bytes).hexdigest()
    capture_fn = runner or capture
    trials = []
    for pair, orders in enumerate(plan["arm_orders"], 1):
        for strategy in orders:
            started = time.perf_counter_ns()
            pending = list(plan["tasks"])
            results = []
            while pending:
                elapsed = (time.perf_counter_ns() - started) / 1e9
                selected, scores = choose(pending, strategy, elapsed)
                sid = f"p{pair}-{strategy}-{selected['task_id']}"
                receipt = capture_fn(
                    root, sid, "affectcontrol-test-project",
                    [sys.executable, "-m", "pytest", "-q", selected["test_file"]],
                    cwd=repo, timeout_s=30,
                )
                finished = (time.perf_counter_ns() - started) / 1e9
                passed = receipt["result"] == "exited" and receipt["exit_code"] == 0
                results.append({
                    "task_id": selected["task_id"],
                    "score_before_execution": scores[selected["task_id"]],
                    "start_elapsed_s": elapsed,
                    "end_elapsed_s": finished,
                    "experimentally_assigned_deadline_s": selected["deadline_s"],
                    "local_exit_zero": passed,
                    "local_exit_zero_before_deadline": passed and finished <= selected["deadline_s"],
                    "source_receipt_trace_sha256": receipt["trace_sha256"],
                })
                pending = [x for x in pending if x["task_id"] != selected["task_id"]]
            trials.append({
                "pair": pair, "strategy": strategy,
                "task_order": [x["task_id"] for x in results],
                "local_test_on_time_rate":
                    sum(x["local_exit_zero_before_deadline"] for x in results) / len(results),
                "local_test_exit_zero": sum(x["local_exit_zero"] for x in results),
                "elapsed_s": (time.perf_counter_ns() - started) / 1e9,
                "observations": results,
            })
    differences = []
    for pair in range(1, pairs + 1):
        arms = {trial["strategy"]: trial for trial in trials if trial["pair"] == pair}
        differences.append(
            arms["affective"]["local_test_on_time_rate"] -
            arms["urgency"]["local_test_on_time_rate"]
        )
    report = {
        "protocol": PROTOCOL, "source_git_sha": head,
        "frozen_plan_sha256": plan_hash,
        "n_pairs": pairs, "n_independent_project_lineages": 1,
        "trials": trials, "arm_orders": plan["arm_orders"],
        "paired_differences_affective_minus_urgency": differences,
        "mean_paired_difference": sum(differences) / len(differences),
        "ci95": None,
        "independent_outcome_acceptance": None,
        "preemptions_observed": 0,
        "deadline_basis": "experimentally_assigned_not_user_observed",
        "evidence_level": "E1",
        "limitation": (
            "Real subprocesses and randomized order, but all work is one "
            "research project and assigned toy deadlines. No actual "
            "running-process preemption, independent outcome oracle, "
            "prospective natural workloads or causal production evidence. "
            "Exit-zero is only a local process result."
        ),
    }
    _write_exclusive(root / "results.json", canonical(report))
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", default=".")
    p.add_argument("--root", required=True)
    p.add_argument("--pairs", type=int, default=2)
    p.add_argument("--seed", type=int, default=20261108)
    a = p.parse_args()
    print(json.dumps(run(a.repo, a.root, pairs=a.pairs, seed=a.seed),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
