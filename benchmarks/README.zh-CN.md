# Benchmark 说明

[English](README.md)

本目录提供的是**工程评估 Harness**，不是已经可以写进论文结论的实验结果。

## Scheduler benchmark

```bash
PYTHONPATH=src python benchmarks/scheduler_benchmark.py --episodes 200 --seed 17
```

每个 episode 会随机生成任务到达时间和持续时间。目前包含：

- 已经在运行的后台任务；
- 一个明确“不急”的噪声任务；
- 一个带 deadline 的紧急任务；
- 显式 immediate 与模型/规则推断 urgent 的混合情况。

同一组场景会分别跑：

- `static`：不使用 affective 抢占；
- `affective`：使用持续状态、control bias 与生命周期抢占/恢复。

输出指标：

- 平均抢占延迟；
- deadline miss rate；
- 相对合成真值标签的错误抢占率；
- 时间窗内连续多次抢占定义的 task thrashing；
- resume success rate；
- 显式 user override compliance；
- preemption / task switch 数量。

这里的 ground truth 是 benchmark 人工定义，不代表人类真实偏好的统计结论。

## 参数敏感性

```bash
PYTHONPATH=src python benchmarks/sensitivity.py
```

当前脚本扫描一个最小 interrupt threshold 网格并输出混淆矩阵计数，目的是直接暴露参数变化对行为的影响。

## 如何报告结果

任何 benchmark 数值都至少应同时记录：

- random seed 与 episode 数；
- 完整 policy config；
- provider config；
- 场景生成器版本；
- static / no-persistence baseline；
- sensitivity 或置信区间。

现阶段 benchmark 的主要用途是发现工程回归与参数敏感性，为后续更严格实验做准备。
