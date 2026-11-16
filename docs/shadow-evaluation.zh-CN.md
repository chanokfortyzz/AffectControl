# AffectControl：影子决策配对评估（v0.2）

这项功能只读取 Pilot 决策数据库和**外部提供**的审核标签，不执行任何真实任务，不修改数据库，也不接管 Sage。

## 一、采集任务与结果

使用 affectcontrol-pilot 在影子模式下记录建议（见 pilot.zh-CN.md）。保留 event_id；任务真实完成情况/中断应不应该发生，由外部环境或与策略隔离的人工审核人员提供**独立标签**。不要将 AffectControl 自身得分、它自己的结论或内部模拟事件当成真值。

标签使用 UTF-8 JSONL，每行一个事件：

~~~json
{"event_id":"demo-001","should_interrupt":false,"reviewer_id":"rater-01","split":"holdout","label_origin":"independent_human"}
~~~

可选追加 evidence_file（可读取的文件路径）和 evidence_sha256（该文件的 SHA-256），以便在评估前校验原始证据字节是否匹配。

注意：reviewer_id 与 label_origin 只是数据提供者的声明，程序**不能鉴别人员身份或标签的独立性**。SHA-256 只校验文件完整性，不能证明判断正确。不能将其写成经过独立验证的心理学结论。

## 二、运行

~~~bash
# 本项目根目录，先按 pilot.zh-CN.md 安装
.venv/bin/python -m affectcontrol.shadow_eval \
  --db .affectcontrol/pilot.sqlite3 \
  --labels /path/to/independent_labels.jsonl \
  --minimum 20
~~~

报告包括：匹配率、有效样本数、按任务聚类的配对 Bootstrap 95% CI、两种策略的正确率/误报/漏报、双方只在自己正确时的次数，以及单列统计用户明确“立即执行”的覆盖规则。

- 样本必须为 holdout，不允许训练集标签混入当前报告。
- 每个 event_id 只能出现一次；不接受不存在的决策 ID。
- 必须给出布尔 should_interrupt 和外部标签来源；所有标签的审核与独立性仍须另行核查。
- 硬覆盖事件与普通事件分开计算，防止“立即执行”提高总分造成错觉。
- sample_gate_met 仅表示最小样本数和任务多样性门槛通过，**不代表生产许可**；production_decision 固定为 NOT_APPROVED。
- 零值的召回分母返回 null，不虚构结果。
- 这是**中断决策的配对分类评估**，不是调度器实际执行结果、因果实验，也不能替代任务正确性评价。

## 三、工程门禁

真实运行接入的前提是：至少 20 个独立、预留的中断情境；审计原始任务是否允许打断（用户授权及执行器安全约束）；策略对同一事件给出建议；由执行器外部人员/测试验证器盲审标签；在固定成本/任务分布下报告对照和失败案例。

另外仍需真实调度器基线（EDF/urgency-only）在**同一段任务轨迹**上的执行成功率、截止期限违约率、抢占恢复、耗时与工具成本。这部分可使用既有 TraceRunner（docs/external-trace-schema.md），不能把影子分类结果当作完成。
