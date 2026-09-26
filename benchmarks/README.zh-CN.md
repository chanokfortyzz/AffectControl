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

## 工作流形态的长时程诊断

`long_horizon_compare.py` 会回放任务到达、需求修改、阻塞/解除阻塞、过期任务取消、用户显式 override、deadline 更新、暂停恢复和完成等事件，并在完全相同的轨迹上比较：静态优先级、EDF、urgency-only 和 integrated affective control。

```bash
python benchmarks/long_horizon_compare.py --episodes 200 --seed 41
```

2026-09-27 的 200 episode 诊断点估计如下（脚本本身还会输出 95% bootstrap 区间）：

| 策略 | Deadline miss | Override compliance | Wrong preemption | Thrashing |
|---|---:|---:|---:|---:|
| static | 0.400 | 0.000 | 0.000 | 0.000 |
| EDF | 0.213 | 1.000 | 0.613 | 0.675 |
| urgency-only | **0.200** | 1.000 | 0.000 | 0.000 |
| affective | 0.298 | 1.000 | 0.000 | 0.000 |

这**不是** AffectControl 优于 baseline 的证据。当前轨迹中 urgency-only 的 deadline 结果最好；EDF 改善 deadline，但出现大量错误抢占和抖动；当前 affective policy 则以部分 deadline 表现换取更少的无效切换。它仍然只是半合成诊断，不是外部效度结果。

## 标定数据分离

`calibration_split.py` 只在训练分区上拟合阈值，冻结后才在 held-out 测试分区报告 Brier/ECE 和阈值指标，避免在最终测试样本上挑选 interrupt threshold。
