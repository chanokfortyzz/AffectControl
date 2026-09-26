# 安全说明

AffectControl 是控制偏置（control bias）库，不是授权系统。它的输出不能被当作执行删除、高权限操作、金融操作、凭据处理、部署或账户变更的权限证明。

集成方必须在情感/动机控制层之外独立执行安全和权限硬门。Appraisal 可以影响软排序、注意力、规划深度、记忆显著性、反思或抢占建议，但不能绕过用户显式约束和外部安全策略。

Appraisal Provider、示例、测试、trace 和 benchmark fixture 中不得包含 API Key、凭据或私有用户数据。
