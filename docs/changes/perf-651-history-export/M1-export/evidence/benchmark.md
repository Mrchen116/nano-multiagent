# 合成历史导出工作量

## Claim / Baseline

验证派生导出是否按新增历史而非全部历史重复序列化/写入。基线为 main `55376c1112ff870837a6ee65febf52e1f3686a9b` 的真实 `NativeHistory`，2026-10-24 在隔离临时目录执行。未读取生产历史。

## Method

Node 24.22.1，Vitest 4.1.11。创建 2048 条 seq 连续的 tool/result 事件，每条 data.text 为 4096 个 ASCII x；每轮再追加 user/message、assistant/message、turn/end 共 3 条。消息文本为轮次加空格及 128 个中文“文”，time 固定 1700000000000，source.kind=user，session id=bench，agentPreset=nano:a:1，cwd 为 mkdtemp 目录。

NativeHistory 使用真实 fs/promises 写入；替换上下文 storageDomain/flush 为确定性成功 fixture，通过注册的 session/event 入口触发。对 writeFile 与 appendFile 包装记录实际 Buffer.byteLength(payload)，并调用原函数执行磁盘写入；每个原始事件 toJSON 计数原始事件实际序列化次数。完成调用 stop，读取 path 和可读副本验证最终行数。初始轮、20 个逐轮等待的新增轮次、20 个同时排队的轮次分别重置计数。一次性脚本不进入长期测试集；永久测试保护相同的输出与工作量边界。

## Result: baseline

| 阶段 | 应用写入字节 | 原始事件序列化数 | 文件写调用数 |
|---|---:|---:|---:|
| 初始 2051 个事件 | 8,541,300 | 2051 | 2 |
| 后续顺序 20 轮 | 171,262,920 | 41,650 | 40 |
| 后续同时排队 20 轮 | 172,492,300 | 43,420 | 40 |

最终原始 JSONL 2172 行（含 header），可读 JSONL 82 行。顺序阶段单次运行约 4479 ms，仅作辅助观察。

## Locator / Limit

执行命令：`pnpm exec vitest run packages/dsh-integration/tests/export-benchmark.tmp.test.ts`（一次性脚本，收尾移除）。本机结果 `/tmp/perf-651-before.json`。这是实际提交给文件系统 API 的逻辑 payload，不含 rename 元数据、文件系统缓存/写放大，也不是硬盘设备物理 I/O 或生产延迟。基线使用同步成功 flush fixture，不测 DSH 持久化性能；真实 DSH 接线由 history.test.ts 单独验证。
