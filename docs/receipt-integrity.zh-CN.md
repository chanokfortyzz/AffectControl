# Sage 执行回执字节完整性核验（只读）

输入是 Sage 的 07-MAC_TASK_STATE.json 快照。这不是新的采集系统、不是验收系统，更不是 Sage 调度执行器。只在操作者明确传入的本地 artifact-root 下读取小型结果文件、对比快照里声称的 SHA-256 和文件字节。不会读取根路径之外的文件、不会调度、不会输出任务 ID 或原始路径。

## 运行

~~~bash
# 第一阶段：只统计快照中有多少结果回执、哈希、可接受的 hash_scope；
# 不指定 artifact-root 就绝不会读取结果文件
.venv/bin/python -m affectcontrol.receipt_audit --input /path/to/07-MAC_TASK_STATE.json

# 第二阶段：确保明确授权且文件处于可信本地目录；再校验文件内容字节
.venv/bin/python -m affectcontrol.receipt_audit \
  --input /path/to/07-MAC_TASK_STATE.json \
  --artifact-root /path/to/allowed/result-directory
~~~

支持 result_hash_scope=utf8-file-bytes-v1、固定 64 位十六进制 result_content_sha256、result_bytes。每个文件最多 32 MiB。快照最多 16 MiB。绝对路径必须实际落在指定 root 下；相对路径相对于 root；解析后的越界路径拒绝，叶子符号链接拒绝。根目录不可简单设置为磁盘根目录（那会扩大授权访问范围）。

报告会区分：source_result_exists_true、valid_sha256_claims、supported_hash_scope、sha256_matched_bytes、sha256_mismatch、artifact_unavailable、out_of_scope_path、source_size_mismatch 等计数。没有可用 root 时只统计来源声称，不进行文件验证。

**hash matched 只能证明读取到的当前文件字节与该快照宣称的哈希一致。** 快照本身可能已过期或由同一个执行器自报，不能独立证明任务是否成功，更不能证明用户授权、抢占安全或回执身份。independently_verified_task_successes 固定为 0；生产决策固定 NOT_APPROVED。

## 不同数据版本

2026-11-17 Mac Obsidian 导出 sage-observational-v1.jsonl 为 37,279 行（SHA256 a9d8cb30...），Sage 在 VPS 报告的是一份 30,528 行的 2026-10-24 版本。它们不是同一批记录，不可跨版本拼接计数或直接比较。该工具输入是另外一种任务状态快照，不能拿 JSONL 当作 07-MAC_TASK_STATE.json 输入。

## 后续

只有当独立、固定的任务测试真正检查成果文件/环境状态，并保留独立的测试运行、权限、时间和来源证据，才有资格计算真实成功率。收集截止期限、剩余工时和签发/有效期可核验的抢占授权之前，所有影子 Context Gate 缺失字段必须保持 abstain。
