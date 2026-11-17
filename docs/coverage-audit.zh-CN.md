# Sage 现有观测数据覆盖率审计（只读）

本功能**复用**已有 Sage exporter 输出，不再建设新的平行抓取器。只对 CSV/JSONL 中已存在的结构化字段做计数，不解读私人任务原文，不输出 task_id；不调用任何 Agent 或派单，不代表科学验证。

## 运行

在 AffectControl Pilot worktree 目录中：

~~~bash
.venv/bin/affectcontrol-coverage-audit \
  --input /Users/chenzhiliang/Documents/obsidian/note/AI-Memory/research/affect-control/exports/sage-observational-v1.jsonl
~~~

也可以运行 Python 模块：

~~~bash
.venv/bin/python -m affectcontrol.coverage_audit --input /path/to/existing-sage-observational.jsonl
~~~

输出聚合：源 SHA-256、总行数、匿名/非匿名任务 ID 数量、各种事件类型计数、是否出现所需五项 context、欠缺字段数、来源中的 preemptible 标志数、被声明为外部标签的行数。报告不会回传任务正文或单独任务 ID。

**非常重要**：Sage 现有 exporter 的 preemptible 字段是源任务标志，不等同于正在运行任务的可抢占授权；原本的 at_s 是时间轴，不等同于截止期限。不能从 source status 推出 should_interrupt 标签；也不能把 E0/E1 的自报成功当独立执行验收。

如果五项结构化 context 不齐，AffectControl context gate 必须 abstain。其五项要求参见 context-gate.zh-CN.md。该程序对超大文件/超长行设置上限；所有结果均为 read_only_audit / NOT_APPROVED。

该脚本只分析现有观测 schema 与覆盖率；任务语义、独立验证者以及生产抢占许可，仍需分别补充。
