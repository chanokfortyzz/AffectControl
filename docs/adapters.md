# Experimental Framework Adapters

[中文](adapters.zh-CN.md)

The adapters are dependency-optional integration helpers, **not official framework integrations** and not authorization layers.

- `LangGraphControlNode`: callable node that accepts/returns graph-state mappings.
- `OpenAIAgentsContext` + `apply_to_openai_context`: stores local control state in an application context object suitable for passing to OpenAI Agents SDK `Runner.run(..., context=...)`.
- `AutoGenControlBridge`: explicit `before_run()` helper for host applications around AutoGen-style task runs.
- `CrewAIFlowControlBridge`: explicit helper for Flow/Crew application state.

The core package does not import any of those frameworks. This avoids version-locking the research harness to fast-moving orchestration APIs.

## Boundary

Adapters expose `ControlBias`; they do not grant tool access, bypass approvals, cancel irreversible operations, or decide whether a framework-specific run is safely preemptible. Those remain host-runtime responsibilities.
