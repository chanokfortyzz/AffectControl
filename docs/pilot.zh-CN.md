# AffectControl Shadow Pilot v0.1

**定位：可运行的本地建议模式试点，不是生产调度器，也不是已验证的情感理论。**

沿用现有 AffectControlHarness、StateEngine、ControlPolicy、MemoryControl；不新建第二套情感算法，不连接 Sage/VPS/S1，不调用模型、工具或网络。

## 安装与运行

在本分支的仓库根目录：

~~~bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m affectcontrol.pilot --db .affectcontrol/pilot.sqlite3 decide \
  --event-id demo-001 --task-id research-001 \
  --text '核对研究数据，今天交付' --priority P2
~~~

结果为机器可读 JSON，包含 recommendation（原控制建议）、baseline（urgency-only 阈值 0.75）、state_step、dispatch_allowed:false。输出不是已经抢占、完成或验证的证明。

只有用户明确要求立即执行，才能传 --immediate；普通紧急文本不能冒充用户硬覆盖。

## 真实任务反馈

任务执行与独立验收发生在 AffectControl 外部：

~~~bash
.venv/bin/python -m affectcontrol.pilot --db .affectcontrol/pilot.sqlite3 feedback \
  --event-id demo-001 --status partial
.venv/bin/python -m affectcontrol.pilot --db .affectcontrol/pilot.sqlite3 report
~~~

可选提交真实产物 SHA-256 完整性校验：

~~~bash
shasum -a 256 /path/to/artifact
.venv/bin/python -m affectcontrol.pilot --db .affectcontrol/pilot.sqlite3 feedback \
  --event-id another-event --status success \
  --evidence-file /path/to/artifact --expected-sha256 REPLACE_WITH_SHA256
~~~

这里的哈希核验只证明提交时文件字节符合预期，不能证明任务正确。reported_outcome 始终是自报，不能冒充独立验收。重复提交同一结果幂等；矛盾二次提交会被拒绝，须另建事件保留审计记录。

## 数据与隔离

- 默认唯一落盘位置是指定 SQLite 数据库及其 WAL/SHM；不会改写 Sage 生产文件。
- 状态按 task_id 独立存储；决策和状态更新在同一个 SQLite 事务提交。
- 对每次决策原文仅存 SHA-256 哈希，不保存原文。仍需避免在命令行输入密码、令牌或私人聊天（终端历史可能记录）。
- event_id 全库唯一；相同请求重放不会重复改变状态；同 ID 不同请求拒绝。
- 只提供建议，不调度、不发布、不提权；情感分数不是授权。
- SQLite WAL 仅适用单主机；禁止跨机器直接共享写同一个数据库。

## 验收及后续边界

已覆盖自动化场景：幂等决策、任务隔离、立即执行硬覆盖、错误闭锁、反馈事务回滚、产物哈希校验、CLI 全链路。

仍未完成：

1. 真实 Agent 执行器至少 20 个经过脱敏的配对任务和工具轨迹，人工先采集，不能接管生产调度。
2. 同任务同资源口径对比 affective reference、urgency-only 和 EDF 的真实任务正确率、时间、成本、安全违规及中断恢复；不以本工具自造标签作为验收。
3. 由独立结果/产物验证器检查正确性；哈希不能代替 QA。
4. 通过风险门禁后才讨论 Sage 影子读取；任何生产接管必须另行授权和有失败回退。

状态：**本地 Pilot 可用；真实调度未验收；科学效果 E0–E1。**
