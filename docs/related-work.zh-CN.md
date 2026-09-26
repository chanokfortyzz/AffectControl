# 相关工作与定位

[English](related-work.md)

AffectControl 应被定位为一个**外部、框架无关的 control-plane harness**。它不声称发现了语言模型内部的情感机制。

## 重要相邻方向

| 方向 | 代表工作 | 意义 | 与 AffectControl 的关系 |
|---|---|---|---|
| 内部情感表征 | *Emotions Where Art Thou*（ICLR 2026）；*Emotion Concepts and their Function in a Large Language Model*（2026） | 发现结构化内部情感表示及因果行为效应 | 机制主张明显更强；与本项目互补而非被替代 |
| representation-level affect steering | E-STEER（2026）；PsySET/steering 相关工作 | 直接干预隐藏表征并改变 agent 行为 | AffectControl 位于模型外部，必须与其比较，不能默认更优 |
| 显式 VAD 动力学 | *Controlling Long-Horizon Behavior in Language Model Agents with Explicit State Dynamics*（2026 preprint） | 用一阶/二阶动力学维护外部 VAD 状态 | 与外部状态思路直接重叠，是重要 baseline |
| 欲望/内在动机 | D2A（ICLR 2025） | 动态欲望驱动自主任务提出与选择 | 动机模型更丰富，可作为自主任务生成 baseline |
| 学习式记忆控制 | AgeMem（ACL 2026）；MemAct（Findings ACL 2026） | 把 memory operation 变成可学习 policy/action | 比启发式 memory salience 更强的 baseline |
| 真实长时程评测 | OSWorld 2.0/2.1；Odysseys | 暴露状态丢失、动态变更和长时程性能坍塌 | 应作为外部效度主要环境 |

## 定位约束

目前站得住的贡献不是“提出新的情感机制”，而是：

1. 提供 task-scoped appraisal/state/control 的可复用控制平面接口；
2. 提供比较不同外部 affective control 方案的实验脚手架；
3. 提供研究 interruption、deadline、resume、memory/reflection coupling、calibration 的 scheduler-level testbed；
4. 提供一个可检验 Jev 类快速、可校准 appraisal 是否优于规则、生成式 appraisal、VAD dynamics 和 representation-level 方法的统一环境。

只有完成正式实证比较后，才应讨论 novelty。

## 参考文献

- Reichman, B., Avsian, A., & Heck, L. *Emotions Where Art Thou: Understanding and Characterizing the Emotional Latent Space of Large Language Models.* ICLR 2026. https://proceedings.iclr.cc/paper_files/paper/2026/hash/51fa846f6b6b463144736fc3c3481f8c-Abstract-Conference.html
- Sofroniew, N. et al. *Emotion Concepts and their Function in a Large Language Model.* 2026. https://www.transformer-circuits.pub/2026/emotions/index.html
- Sun, M. et al. *How Emotion Shapes the Behavior of LLMs and Agents: A Mechanistic Study (E-STEER).* arXiv:2604.00005, 2026. https://arxiv.org/abs/2604.00005
- Subaharan, S. *Controlling Long-Horizon Behavior in Language Model Agents with Explicit State Dynamics.* arXiv:2601.16087, 2026. https://arxiv.org/abs/2601.16087
- Wang, Y. et al. *Simulating Human-like Daily Activities with Desire-driven Autonomy.* ICLR 2025. https://proceedings.iclr.cc/paper_files/paper/2025/hash/513cb685f67550dbd133b81a7a24249f-Abstract-Conference.html
- Yu, Y. et al. *Agentic Memory: Learning Unified Long-Term and Short-Term Memory Management for Large Language Model Agents.* ACL 2026. https://aclanthology.org/2026.acl-long.981/
- Zhang, Y. et al. *Memory as Action: Autonomous Context Curation for Long-Horizon Agentic Tasks.* Findings of ACL 2026. https://aclanthology.org/2026.findings-acl.956/
- Yuan, M. et al. *OSWorld2.0: Benchmarking Computer Use Agents on Long-Horizon Real-World Tasks.* 2026. https://osworld-v2.xlang.ai/
- Jang, L. K. et al. *Odysseys: Benchmarking Web Agents on Realistic Long Horizon Tasks.* arXiv:2604.24964, 2026. https://arxiv.org/abs/2604.24964
