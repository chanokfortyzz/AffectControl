# External Trace Schema

[中文](external-trace-schema.zh-CN.md)

`load_jsonl_trace()` imports externally collected task/event timelines so evaluation does not have to depend on the repository's own scenario generator.

Each line is JSON:

```json
{"at_s": 12.5, "kind": "arrive", "task_id": "task-7", "payload": {"text": "review draft", "duration_s": 30, "priority": "P2", "deadline_s": 80}}
```

Supported event kinds are currently:

- `arrive`
- `revise`
- `block`
- `unblock`
- `cancel`
- `control`

Common payload fields include `text`, `duration_s`, `duration_delta_s`, `priority`, `deadline_s`, `preemptible`, `goal_id`, `immediate`, `expected_interrupt`, and arbitrary `metadata`.

## External-validity rule

Importing a trace does not make an experiment externally valid. A publishable protocol should document the trace source, sampling population, inclusion/exclusion criteria, time normalization, task-completion oracle, interruption labels, privacy scrubbing, and train/validation/test separation.

`interrupt_overlay()` can add controlled interruption events to a frozen external trace. Overlay events and original events should be stored separately so injected conditions remain auditable.
