# Sage 历史任务：真实产物的独立窄项验收

这个检查不是情感评分，也不接管 Sage。它把历史任务归档中的**原始请求**、当前结果文件、哈希回执与 local-worker 事件轨迹交叉核验。验证由单独、只读的 Python 程序执行，任务执行器不会参与检查。验收规则是在历史结果被发现后明确选定的，因此属于 **post-hoc 探索性检查，不是事先冻结的盲评 gold label**。

## 已核实的具体缺陷（2026-11-17）

- 原始任务：一条历史 local-worker 测试任务（真实 ID 仅保存于私有合同）。
- 归档原始任务描述明确要求「整理成三条中文要点」；验收标准还要求任务包、local-worker 领取和轨迹有 packaged/claimed/finished 事件。
- 原任务归档记为 done，local-worker 轨迹里存在 packaged/claimed/finished 事件。
- 保存的结果文件 239 bytes，SHA-256 与源快照声明一致，但内容只有一个 read_file 的 tool_call 片段，**没有三条中文要点**。
- 该产物有明确的**窄项验收失败**。这不是凭推测判定全部任务失败，也不是证实 AffectControl 比 Sage 好。

## 使用

实验性 contract 存放在 Mac 本地 Obsidian 既有 research/affect-control/private/labeling/2026-11-17/，避免将源任务标识与任何私人路径提交到公开 GitHub。

~~~bash
cd ~/Desktop/_项目/AffectControl-pilot-20261117
.venv/bin/affectcontrol-acceptance-probe \
  --contract ~/Documents/obsidian/note/AI-Memory/research/affect-control/private/labeling/2026-11-17/local-worker-three-bullets-contract.json \
  --snapshot ~/Documents/obsidian/note/SAGE-MAC-BRIDGE/07-MAC_TASK_STATE.json \
  --archive ~/Documents/obsidian/note/SAGE-MAC-BRIDGE/02-MAC_TASK_QUEUE-ARCHIVE.md \
  --trace ~/Documents/obsidian/note/AI-Memory/local-worker-task-trace.jsonl \
  --artifact-root ~/Documents/obsidian/note
~~~

前提是这个 root 得到文件所有者授权；程序仅能从此范围内读取快照、归档、轨迹、合同和结果。输入和结果大小受限。输出仅包含匿名 case ID、源文件哈希、检查数字、窄项 verdict，不暴露原始任务文字、路径或内容，也不自动给 Sage 派单。

当前 contract 支持一个明确类型：原任务归档确实要求 3 条中文要点，结果应含 3 条带中文的 Markdown 项目符号/编号，而且不能只有工具调用。仅对这个**特定语义要求**给出 PASS/FAIL，其他任务类型需要分别定义原始可检验合同，**不可自动套用相同评分**。轨迹事件为执行器自己报告，不能视为独立成功证据。

目前这些检查是**产物缺陷发现和事后核实**，不等于盲审或科学实验结果。不可把 NARROW_ACCEPTANCE_PASS 记为任务成功，亦不可把这一次 QA 缺陷当作 AffectControl 调度优越性的统计证据。

下一步由未接触原执行输出的独立审核者，基于任务目标先冻结一批验收合同，再审阅保留的隐藏产物，签收证据，最后才可能提供真正的 holdout labels。现存的旧任务只可作探索性工程审计。
