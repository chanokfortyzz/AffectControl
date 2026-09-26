# 贡献指南

核心库必须保持框架无关、可测试，并且不得包含任何特定产品的私有状态。新增 appraisal provider 不得内嵌密钥；新增控制策略必须保留用户显式约束和安全硬门。凡是改变控制行为的提交，应补充测试，并在适用时提供 benchmark 证据。

设计说明见 [README.zh-CN.md](README.zh-CN.md)，研究与评估计划见 [docs/research-plan.zh-CN.md](docs/research-plan.zh-CN.md)。
