# 实验性框架适配器

[English](adapters.md)

这些 adapter 是**可选依赖的集成 helper**，不是任何框架的“官方适配”，也不是授权层。

- `LangGraphControlNode`：接收/返回 graph state mapping 的 callable node。
- `OpenAIAgentsContext` + `apply_to_openai_context`：把本地控制状态放进可传给 OpenAI Agents SDK `Runner.run(..., context=...)` 的应用 context。
- `AutoGenControlBridge`：宿主在 AutoGen 风格 task run 前显式调用的 `before_run()` helper。
- `CrewAIFlowControlBridge`：用于 Flow/Crew 应用状态的显式 helper。

核心包不会强制 import 这些框架，避免研究 Harness 被快速变化的 orchestration API 锁死版本。

## 边界

Adapter 只暴露 `ControlBias`；它们不会赋予工具权限、绕过审批、取消不可逆操作，也不会自行判断某个框架运行是否可以安全抢占。这些责任仍属于宿主 runtime。
