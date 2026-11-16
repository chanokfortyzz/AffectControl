# AffectControl：批量影子任务接入

适用于已经有 Agent 任务队列快照的情况。**只处理脱敏的离线输入**，不会直接接管 Sage、Clipz 或任何执行器，不会发布、执行或抢占任务。

## 输入

UTF-8 JSONL，每行一项；上限 1 MiB、1000 行有效任务：

~~~json
{"event_id":"task-2026-11-01-a","task_id":"research-01","text":"review this report","priority":"P2","immediate":false}
{"event_id":"task-2026-11-01-b","task_id":"documentation-02","text":"prepare a summary","priority":"P3"}
~~~

event_id 必须唯一，必须有 task_id 和 text。输入只允许这五个字段；缺省 priority=P2、immediate=false。请勿将真实对话原文、账号、密钥、私人资料或未经授权的 Agent 内部消息填入 text。

## 运行

~~~bash
.venv/bin/affectcontrol-shadow-ingest \
  --db .affectcontrol/pilot.sqlite3 \
  --input /path/to/sanitized_tasks.jsonl \
  --output .affectcontrol/recommendations-20261117.jsonl
~~~

输出是影子建议 JSONL，不是执行指令；console 还会打印输入与输出的 SHA-256。若不写 --output，则输出到 stdout。它不包含原任务 text。

用户明确要求“立即”时，外部导出器必须先独立核对授权，且操作者必须明确附加 --allow-explicit-user-immediate；这个选项仍**不会**激活执行器。

## 故障与重放

- 输入完整预校验后才开始写数据库；错误字段、重复 event_id 和越权 immediate 直接拒绝。
- 数据库单条事务；意外中断可能让前几条被写入，但原封不动重放相同文件会幂等返回。改变同一个 event_id 的内容会拒绝。
- 不允许覆写既有输出文件，也不允许覆盖输入或数据库；应换一个输出文件名重试。
- 结构化建议可供单独的外部系统审阅，但**任何生产执行均须额外开发权限隔离、审批、灾难回退与验收**。

配对评估参见 shadow-evaluation.zh-CN.md。批量导入本身不形成独立标签，也不算科学证据。
