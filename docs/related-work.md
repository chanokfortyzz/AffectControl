# Related Work and Positioning

[中文](related-work.zh-CN.md)

AffectControl should be positioned as an **external, framework-neutral control-plane harness**. It does not claim to discover emotion mechanisms inside language models.

## Important adjacent directions

| Direction | Representative work | Why it matters | Relation to AffectControl |
|---|---|---|---|
| Internal emotion representations | *Emotions Where Art Thou* (ICLR 2026); *Emotion Concepts and their Function in a Large Language Model* (2026) | finds structured internal emotion representations and causal behavioral effects | stronger mechanistic claim than AffectControl; complementary, not displaced |
| Representation-level affect steering | E-STEER (2026); PsySET/representation steering work | directly changes hidden representations and agent behavior | AffectControl operates outside the model; must be compared rather than assumed superior |
| Explicit VAD dynamics | *Controlling Long-Horizon Behavior in Language Model Agents with Explicit State Dynamics* (2026 preprint) | persistent external VAD state with first/second-order dynamics | directly overlaps the external-state idea; important baseline |
| Desire/intrinsic motivation | D2A, ICLR 2025 | dynamic desires drive autonomous task proposal/selection | richer motivation model; useful baseline for autonomous task generation |
| Learned memory control | AgeMem, ACL 2026; MemAct, Findings ACL 2026 | memory management becomes a learned policy/action | stronger learned-memory baselines than heuristic memory salience |
| Real long-horizon agent evaluation | OSWorld 2.0 / 2.1; Odysseys | realistic tasks expose state loss, dynamic updates, and long-horizon collapse | preferred external-validity environments |

## Positioning constraint

The defensible contribution today is not “a new emotion mechanism.” It is:

1. a reusable control-plane interface for task-scoped appraisal/state/control;
2. an experimental scaffold for comparing external affective control variants;
3. a scheduler-level testbed for interruption, deadline, resumption, memory/reflection coupling, and calibration;
4. a practical place to evaluate whether fast calibrated appraisal (including Jev-like fast structured appraisal models) adds value over rules, generative appraisal, VAD dynamics, and representation-level alternatives.

Novelty should only be claimed after formal empirical comparison.

## References

- Reichman, B., Avsian, A., & Heck, L. *Emotions Where Art Thou: Understanding and Characterizing the Emotional Latent Space of Large Language Models.* ICLR 2026. https://proceedings.iclr.cc/paper_files/paper/2026/hash/51fa846f6b6b463144736fc3c3481f8c-Abstract-Conference.html
- Sofroniew, N. et al. *Emotion Concepts and their Function in a Large Language Model.* 2026. https://www.transformer-circuits.pub/2026/emotions/index.html
- Sun, M. et al. *How Emotion Shapes the Behavior of LLMs and Agents: A Mechanistic Study (E-STEER).* arXiv:2604.00005, 2026. https://arxiv.org/abs/2604.00005
- Subaharan, S. *Controlling Long-Horizon Behavior in Language Model Agents with Explicit State Dynamics.* arXiv:2601.16087, 2026. https://arxiv.org/abs/2601.16087
- Wang, Y. et al. *Simulating Human-like Daily Activities with Desire-driven Autonomy.* ICLR 2025. https://proceedings.iclr.cc/paper_files/paper/2025/hash/513cb685f67550dbd133b81a7a24249f-Abstract-Conference.html
- Yu, Y. et al. *Agentic Memory: Learning Unified Long-Term and Short-Term Memory Management for Large Language Model Agents.* ACL 2026. https://aclanthology.org/2026.acl-long.981/
- Zhang, Y. et al. *Memory as Action: Autonomous Context Curation for Long-Horizon Agentic Tasks.* Findings of ACL 2026. https://aclanthology.org/2026.findings-acl.956/
- Yuan, M. et al. *OSWorld2.0: Benchmarking Computer Use Agents on Long-Horizon Real-World Tasks.* 2026. https://osworld-v2.xlang.ai/
- Jang, L. K. et al. *Odysseys: Benchmarking Web Agents on Realistic Long Horizon Tasks.* arXiv:2604.24964, 2026. https://arxiv.org/abs/2604.24964
