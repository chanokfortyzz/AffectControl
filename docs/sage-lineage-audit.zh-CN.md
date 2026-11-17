# Sage 任务生命周期只读核对

使用已有脱敏 sage-observational-v1.jsonl，从来源事件中统计每个 task_id 出现过哪些状态。**不会重新采集 Sage 数据、下发任务、修改调度或推断中断标签**。程序不输出任务 ID、任务文本、原始状态值或轨迹。

## 运行

~~~bash
.venv/bin/affectcontrol-lifecycle-audit \
  --input /Users/chenzhiliang/Documents/obsidian/note/AI-Memory/research/affect-control/exports/sage-observational-v1.jsonl
~~~

输出项目：
- task_lineages_with_events：当前 JSONL 的有效事件记录里，不重复的任务 ID 数。
- tasks_with_recorded_terminal_event：有 task-finished 或 task-finished-by-lease 标记的任务数量。
- tasks_with_recorded_review_passed：有 review-passed 标记的任务数量。
- tasks_with_both_terminal_event_and_review_marker：同时包含上述两类标记的任务数量；不一定同一次尝试。
- tasks_with_lease_terminal_without_explicit_finish：只出现 lease 终止而无显式 task-finished 标记的任务数量。
- tasks_with_retry_event：包含任务重新打开标记的任务数量。

任务快照另属匿名快照粒度，只计数、不与真实 task_id 推断关联。**终止、review-passed 或成功自报都不能替代独立验收，也不能直接计算 Sage 任务成功率**。输出 independently_verified_successes=0 仅表示此工具未核验任何独立验收证据，不代表现实中成功为零。

结果带文件 SHA-256、行数、事件类型计数和数据限制说明；缺失或未知的事件不会被当成成功/失败。所有输出 dispatch_allowed=false、production_decision=NOT_APPROVED。

## 后续数据对接

既有 Sage 源快照提供 process_alive、claimed、packet_status 和部分 urgency；可在未来作为只读观测或候选线索，但 **不得**自动转换为当前运行任务可安全抢占、真实截止时间、任务剩余计算时间等 Context Gate 字段。

源头需补充可追溯时间戳、主体权限、任务尝试 ID、外部验证器结果/可读证据引用，并将新的标注数据与算法输出隔离。先进行影子记录；完整同条件配对验收前不接管生产。
