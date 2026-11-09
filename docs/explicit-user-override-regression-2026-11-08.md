# Explicit user immediate override regression and repair — 2026-11-08

## Trigger

The preceding exploratory AB/BA study found an uncalibrated
**base-priority versus lexical urgency ranking conflict**. That study
did **not** set the explicit immediate-user flag. It was not evidence
that explicit override was defective.

A subsequent separately factored examination varied:

- Incoming base task priority: **P0, P1, P2, P3**.
- Incoming wording: **neutral** vs **"urgent ... right now"**.
- User immediate flag: **false** vs **true**.
- A fixed **preemptible P0 background task** with a tight deadline
  versus an incoming task with a later deadline.

The reference Affective scheduler returned a higher weighted score for
the background (2.0 vs. 1.88 on the explicit branch), so an explicit
user override was ignored even when its ControlPolicy correctly
generated `effective_priority=P0`, `should_interrupt=True`, and
`explicit_user_immediate_hard_override` in the reasons.

**Red tests, recorded before the patch:** all eight immediate-flag
conditions across 4 priorities × 2 wording states failed to preempt.
A separate already-queued override also lost to a high-scoring rival.
The full red run also contained a test-design failure caused by an
incoming test task completing before the assertion; its test duration
was corrected before final validation. No favorable effect is claimed
from that test-design failure.

## Fix

The research branch now treats an **authenticated hard-override control
reason AND user-origin explicit metadata flag** as a scheduling
constraint in the `affective` strategy, rather than relying on
the ordinary weighted score comparison:

1. When an explicit override is waiting, it is considered before
   lower-authority ordinary queued tasks. Multiple explicit commands
   are ordered FIFO.
2. If the running task is **preemptible** and is not itself an
   active explicit override, a waiting explicit command can preempt
   without the usual weighted-score margin.
3. If the running task is nonpreemptible, it is not forcibly
   interrupted. An active explicit command is not displaced by
   ordinary priorities.
4. Merely spoofing `metadata.explicit_override=True` without the
   trusted ControlPolicy hard-override reason does not elevate work.
5. The benchmark `static`, `urgency`, and `edf` strategies keep
   their original comparison behavior. No score weights or
   emotional-state features were retuned.

The new regression suite covers all 8 explicit combinations,
nonpreemptibility, queued scheduling, active override protection,
spoofed metadata, baseline isolation, lexical urgency without explicit
user authorization, FIFO explicit commands and full
`TraceEvent(immediate=True) → ControlPolicy → AffectiveScheduler`
integration. This tests **the current reference implementation's
contract**, not its superiority on an independently sampled workload.

## Scientific and operational boundary

A direct human user intent is not cryptographically established merely
by adding a metadata flag. The upstream task intake must authenticate
the user request and prevent an Agent or untrusted content from forging
the hard-override ControlPolicy reason.

The fix changes the research reference scheduler semantics and may
alter what gets preempted. It must **not** be deployed to Sage
production automatically. Prospective independent acceptance,
user-supplied priority/deadline ground truth and safety checks are
still missing. AffectControl remains **E1**.

To reproduce:

```bash
uv run --extra dev pytest -q tests/test_explicit_override_priority.py
uv run --extra dev pytest -q
```


## Preemption deadline tradeoff, disclosed in a fixed simulation

A separate deterministic guardrail scenario has one P0 preemptible
background task (4 s work, deadline at t=5) and one incoming P3
task (3 s work, deadline at t=20), arriving at t=1. The only
manipulation is the authenticated explicit user-immediate flag.

| Scenario | Background done | Incoming done | Preemptions | Deadline misses |
|---|---:|---:|---:|---:|
| Explicit flag absent | t=4 | t=7 | 0 | 0 |
| Explicit flag present | t=7 | t=4 | 1 | 1 |

These are **model-simulated** outcomes under specified deterministic
durations, not natural external deadlines or real Agent latencies.
They establish a concrete safety tradeoff: honoring an explicit user
command can cause a previously timely task to miss its deadline.
The existing research comparison should therefore report deadline
misses, displaced task age, override compliance and interruption cost
together. The desired choice among conflicting user instructions and
deadlines needs an explicit owner policy; the model must not silently
claim that override compliance always improves task performance.
