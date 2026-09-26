# Policy Parameters

[中文](policy-parameters.zh-CN.md)

All numerical values shipped in the config dataclasses are **uncalibrated reference fixtures**. They do not represent recommended defaults. Prefer the explicit `reference_policy()` opt-in for diagnostics; it is tagged `uncalibrated_reference` and warns by default.

## Parameter groups

### `RuleProviderConfig`

Controls the deterministic fallback baseline: routine/urgent/immediate urgency, salience, arousal, tension, interruption value, memory value, and punctuation contribution.

These values are intentionally isolated from `KeywordRuleBaseline` implementation so experiments can replace them without code changes.

### `StateConfig`

Controls:

- appraisal blending factor `alpha`;
- per-dimension decay half-lives;
- success/partial-success tension release;
- failure tension/salience increase;
- certainty/competence outcome updates.

A single global half-life is supported only as a testing convenience. Research runs should record the full per-dimension configuration.

### `MemoryPolicyConfig`

Contains weights for:

- affect contribution to memory salience;
- relevance/recency contribution;
- reflection triggering;
- reflection threshold.

`MemoryControl` is the only component that computes these outputs.

### `ControlPolicyConfig`

Contains:

- affective drive weights;
- interrupt appraisal-vs-drive mixing;
- interrupt threshold;
- one-level and two-level soft priority boost thresholds;
- planning-effort thresholds;
- attention weights.

Explicit user `immediate` bypasses these soft thresholds and remains a hard invariant.

### `SchedulerConfig`

Contains:

- simulation quantum;
- priority/affect/deadline scoring weights;
- deadline horizon;
- switch penalty;
- preemption margin;
- thrashing window and minimum preemption count.

These values define the experimental reference scheduler, not a production SLA.

## Why no claim is attached to defaults

The same policy can behave differently when:

- task arrival distributions change;
- deadlines become tighter or looser;
- provider calibration changes;
- task durations change;
- state decay interacts with sparse or dense events;
- preemption costs differ across runtimes.

Therefore, a fixed set of defaults cannot be defended by code inspection alone.

## Required evaluation before claims

At minimum:

1. sweep thresholds and major weights;
2. report outcome sensitivity;
3. use held-out scenario distributions;
4. separate provider calibration from control-policy tuning;
5. compare against static and non-persistent baselines;
6. report false interruption and thrashing costs, not only deadline gains.

Run:

```bash
PYTHONPATH=src python benchmarks/sensitivity.py
```

This script is only a starting grid. Larger studies should use reproducible search/fitting code and publish the full parameter surface.
