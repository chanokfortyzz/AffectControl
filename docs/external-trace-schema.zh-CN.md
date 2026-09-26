# 外部轨迹 Schema

[English](external-trace-schema.md)

`load_jsonl_trace()` 用于导入外部收集的任务/事件时间线，从而避免所有实验都依赖仓库自己生成的场景。

每行一个 JSON：

```json
{"at_s": 12.5, "kind": "arrive", "task_id": "task-7", "payload": {"text": "review draft", "duration_s": 30, "priority": "P2", "deadline_s": 80}}
```

当前支持 `arrive`、`revise`、`block`、`unblock`、`cancel`、`control`。常见 payload 字段包括 `text`、`duration_s`、`duration_delta_s`、`priority`、`deadline_s`、`preemptible`、`goal_id`、`immediate`、`expected_interrupt` 与自定义 `metadata`。

## 外部效度规则

“能导入外部 trace”不等于“已经有外部效度”。正式实验必须记录轨迹来源、样本总体、纳入/排除标准、时间归一化方式、完成判定、抢占标签、隐私脱敏以及 train/validation/test 划分。

`interrupt_overlay()` 可以在冻结的外部轨迹上注入受控 interruption。原始事件和 overlay 事件应分开保存，保证实验条件可审计。
