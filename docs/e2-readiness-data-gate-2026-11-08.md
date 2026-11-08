# E2 evidence admission audit: real S1 and Agent-eval sources

Date: November 8, 2026. Outcome: No E2-ready episodes found; E1 remains.

## Actual source coverage

The read-only auditor examines:
- 202 pseudonymous S1 watcher events. These are events, not 202 independent tasks.
- 196 pseudonymous S1 shadow events. None has nonnull independent acceptance or test-evidence fields.
- Six Agent-evaluation run summaries (B2/B3), whose success and workflow-complete labels are source-reported rather than independently verified.

Original log files remain gitignored and are not published. A source SHA256 is a change detector, not third-party attestation.

The observed number of complete E2-admissible task episodes is ZERO. This does not mean all tasks failed or that no useful tasks exist elsewhere.

## Admission gaps

| Required evidence | Current status |
|---|---|
| Original user request and authentic arrival | Partial pseudonymous task event timestamps only |
| Real user-imposed deadline, recorded before execution | Missing |
| Trusted S1 to Sage Bus identity association | Missing |
| Independent, read-only environment outcome judgment | Missing |
| Multiple independent task/project lineages | Not proven |
| Frozen comparison allocation or usable action propensities | Missing |

The analyzer deliberately never joins unlike pseudonymous identifiers, even if the strings look similar. An Agent summary that says "passed" is NOT an independent success oracle; missing acceptance remains UNKNOWN rather than being turned into a negative label.

## Executable next-stage research protocol

1. At the trusted intake boundary, log one opaque task identifier, a hash of the user-origin instruction, the original arrival timestamp, explicit immediate/priority flag, any real deadline with its source evidence, and an acceptance criterion frozen before execution. Do not infer deadlines from HPC requested runtimes or benchmark timeouts.
2. Link start, pause, resume and finish using a verified shared task correlation ID. Keep observed wall-clock time separate from active compute time and estimates. Do not derive process duration from isolated status events.
3. Have a separate read-only verifier inspect actual environment state against the original task criterion. It should record pass, fail, unknown, or not-assessable, including conflicting and revoked outcomes. Executor self-report and repository-wide CI cannot self-approve.
4. Preregister treatment allocation/propensity capture, target population, independent task lineages, primary and guardrail endpoints, uncertainty, and what to do when user-immediate commands compete with deadlines. Run prospective treatment allocation only in an approved isolated environment.

LongHorizon-Harness (Ma et al., 2026, arXiv:2608.01964) uses a Manage-Execute-Audit design with read-only outcome checks. REALM-Bench (Geng and Chang, KDD 2026, DOI 10.1145/3770854.3785692) covers designed dynamic disruptions. Both inform the protocol but do not substitute for actual independent task evidence.

Nothing here authorizes automatic Sage production dispatch or claims an E2 experiment has begun.

## Reproduce

From the research repo, run:

    uv run --extra dev python -m benchmarks.e2_evidence_census \
      --s1-watch /Users/chenzhiliang/coding-service/agent-eval/adaptive/s1_watch/changes.pseudonymous.jsonl \
      --s1-shadow /Users/chenzhiliang/coding-service/agent-eval/adaptive/live_shadow/s1_shadow_events_pseudonymous.jsonl \
      --paired /Users/chenzhiliang/coding-service/agent-eval/experiment-p1/paired-results.jsonl \
               /Users/chenzhiliang/coding-service/agent-eval/experiment-p2/paired-results.jsonl \
      --out .research-data/e2-evidence-20261108/new-census-id.json

    uv run --extra dev pytest -q tests/test_e2_evidence_census.py

Use a new output filename each time; the audit does not overwrite evidence.

## Source expansion: archived executor-separated hidden tests

After the first summary-only census, three historical coding tasks
and six B2/B3 executor runs were found with evaluator-only hidden
tests and hash-checkable logs. Six isolated reruns found five passes
and one failure, consistent with the archived hidden outcomes.
This is stronger evidence for coding task checks than self-reported
summary flags, but is neither a natural user deadline nor an
AffectControl-versus-urgency policy trial. Thus there remain zero
E2-eligible AffectControl task episodes. Full detail is in
agent-eval-hidden-oracle-recheck-2026-11-08.md in this docs folder.
