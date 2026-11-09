# Executor-separated hidden test verification of three coding tasks

Date: November 8, 2026. Research level: E1.

## Finding

The earlier E2 census inspected 202 S1 watch events, 196 S1 shadow
events and six compact Agent-evaluation summaries. These alone do not
establish independent task acceptance. An additional source inspection
of the separate local agent-eval project revealed archived evaluator-
only hidden unittest scripts and execution logs for three coding
tasks, each performed in B2 and B3 workflow variants.

Those hidden tests were not in the worktrees exposed to the coding
agents, but their authoring time has no third-party attestation.
This is an executor-separated code test oracle, NOT independent human
business acceptance or an AffectControl scheduling trial.

## Actual fresh execution

For each of the six historical coding worktrees, the auditor:
- Verified the source worktree's git HEAD against task.json's frozen
  fixture commit.
- Verified hidden-test suite bytes against the fixed SHA256 from
  the external evaluator code.
- Checked that both archived public and hidden evaluator logs matched
  their stored SHA256 hashes.
- Copied backend.py and easylap.py into a new isolated temporary
  directory without altering the original worktrees.
- Executed the frozen hidden tests in a fresh Python subprocess and
  compared the result to the archived evaluator outcome.
- Retained only aggregate scores, source hashes and exit metadata;
  no task prompts, private log text, credentials or raw stdout/stderr
  were committed.

| Task | B2 hidden tests | B3 hidden tests |
|---|---|---|
| DEDUP-001 | 2/2 pass | 2/2 pass |
| UNKNOWN-002 | 2/2 pass | 2/2 pass |
| PIPELINE-003 | 3/3 pass | 3 executed, suite failed |

**Five of six independent-of-executor hidden suites passed; one
failed.** All archived hidden pass/fail results were reproduced and
all public/hidden archived log hashes matched. The negative result
was not changed or excluded.

Frozen evaluator suite hashes:
- Experiment P1: 8d879c3a8b431cca5c1796c623de41f5587af908bea43b03057008d2348da516
- Experiment P2: 645d9718658b6df72088de99050d3b631a421d89dba4367d1220a0bd8ed79af9

The result certifies only the currently preserved worktree snapshots;
there is no independent signed snapshot proving the code was bit-for-
bit identical at original evaluation time. The evaluator is local,
not a third-party independent institution.

## Why E2 remains unavailable

B2/B3 refer to different coding workflows, not AffectControl versus
urgency-only scheduling. The three task specifications are not a
population of independent real-world scheduling sessions. There is
no authentic user deadline, no user preference label for interruption,
no verified S1-to-Bus correlation, and no randomly allocated
AffectControl treatment.

These independent-of-executor hidden tests refine our statement about
available evidence, but do not upgrade any task episode to E2.

## Reproduce on authorized local machine

From the AffectControl research repository:

    uv run --extra dev python -m benchmarks.agent_eval_hidden_recheck \
      --agent-eval-root /Users/chenzhiliang/coding-service/agent-eval \
      --python /Users/chenzhiliang/coding-service/raceline-team/.venv/bin/python \
      --out .research-data/e2-evidence-20261108/another-hidden-recheck.json

    uv run --extra dev pytest -q tests/test_agent_eval_hidden_recheck.py

Use a new report filename. The result is stored in ignored local
research data; the source worktrees remain unchanged.
