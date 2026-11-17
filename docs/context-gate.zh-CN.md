# Context Gate：可解释、保守的任务判断

这个模块是现有 AffectControl 情感策略之外的一条**独立运维规则基线**，不会执行任务、不会部署、不会接管 Sage。所有数值来自调用方提供的外部事实，目前不验证其来源。

## 输入五个字段

~~~json
{
  "current_task_running": true,
  "current_task_preemptible": true,
  "task_blocked": false,
  "seconds_until_deadline": 180,
  "estimated_work_seconds": 300
}
~~~

- current_task_running：是否确实有正在执行的任务。
- current_task_preemptible：当前运行任务能否被安全暂停。该限制由执行器与授权规则决定，不能由情感分数推翻。
- task_blocked：候选任务是否因依赖、资源或权限不可用而阻塞。
- seconds_until_deadline：采集时刻到截止期限的秒数，非负。
- estimated_work_seconds：估计候选任务剩余执行时长，非负；估算不等于真实耗时。

字段缺失时输出 abstain，明确提示缺什么；不可凭任务文本捏造。负数、NaN、无限值及非布尔类型均被拒绝。

## 单任务使用

将上述 JSON 保存为一个已脱敏本地文件 context.json。

~~~bash
.venv/bin/affectcontrol-pilot \
  --db .affectcontrol/pilot.sqlite3 decide \
  --event-id isolated-1 --task-id job-001 \
  --text "review report" --priority P2 --context-file context.json
~~~

输出中：

- recommendation：原未校准情感策略，仅供实验；
- baseline：关键词紧迫度基线，仅供比较；
- operational_gate：独立运维门禁，包含 verdict、missing_fields、deadline_slack_s 及 would_interrupt；
- dispatch_allowed:false：不会执行任何任务。

截止期限余量 = seconds_until_deadline - estimated_work_seconds。如果余量≤0，则只表示根据目前的估计存在截止期限风险，可以提议讨论抢占，不意味着已经取得授权，也不代表抢占一定是最佳策略。余量为正不代表其他风险不存在。

当前任务不可中断时，门禁给出 safety_hold。用户明确立即处理仍可以获得原策略 P0 优先级，但不能突破运维层的不安全抢占约束。

## 批量使用

JSONL 每行可以附加 context，也可以缺省：

~~~json
{"event_id":"e1","task_id":"t1","text":"check documentation","context":{"current_task_running":true,"current_task_preemptible":true,"task_blocked":false,"seconds_until_deadline":60,"estimated_work_seconds":120}}
{"event_id":"e2","task_id":"t2","text":"check documentation"}
~~~

~~~bash
.venv/bin/affectcontrol-shadow-ingest --db .affectcontrol/pilot.sqlite3 \
  --input sanitized-tasks.jsonl --output .affectcontrol/recommendations.jsonl
~~~

第二条应该弃权，不得臆测 deadline 等字段。相同 event_id 的完全相同输入幂等；修改上下文会被作为冲突拒绝。

## 配对评估

得到独立的 holdout 人工/外部测试标签后，运行 affectcontrol-shadow-eval。新版报告有 context_gate.non_override_coverage（非硬覆盖事件的上下文覆盖率）和三种规则在同一已覆盖子集上的分类指标。上下文门禁是一个独立比较器，不能把它的成绩算成情感控制策略的效果。缺失上下文的样本不能按预测“不打断”计算。

## 真实接入门槛

现有 AgentEval/RaceLine 的四个工程任务候选只有标题与拟定验收要点，没有可核对的剩余期限、耗时、运行任务和可抢占性，不能真实判断是否需要抢占；应全部 abstain。需要外部授权、脱敏元数据、真实执行回执及独立审核数据才能进一步作效果结论。
