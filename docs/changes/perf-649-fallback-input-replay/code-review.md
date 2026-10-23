# Code Review: perf-649

## Round 1

- reviewer: `/root/static_review`，未参与本 unit 的实现；本轮按 `change-code-review` 独立裁决。
- review_mode: `full`。
- executed_base: `52b9a1ac831cc7f92709d12764cdd1a9410dea0f`。
- validated_at: `986cb0a237831795a2964e598112a501cd007d66`。
- diff: `52b9a1ac831cc7f92709d12764cdd1a9410dea0f...986cb0a237831795a2964e598112a501cd007d66`。
- checkout: `.worktrees/unit-perf-649`，branch `unit/perf-649`；受审前 HEAD 与 validated_at 一致且工作区干净。
- completed_at: `2026-10-23T23:24:33+08:00`。

## Verdict

**PASS — 无存活代码问题。**

```json
[]
```

## Coverage and reasoning

完整阅读 6 个 diff 文件，并回查 `inputEvidence`、ModelFallback 的 attach/observe/evidence/schedule、ModelPolicy 装配和 `session.lookup` 的真实调用方。

- `packages/dsh-integration/src/input-evidence.ts:54` 的新投影保持两条独立 inbox 队列，以原生 splice 处理默认 removedCount、负下标、替换和重复 ID。旧单 ID 投影在非 canceled removal 或 user/message 时更新 turn；新 Map 对每个 ID 执行同样更新，canceled removal 不改旧归属。两者均在 turn/end 后清空当前 turn，因此 out-of-turn 消息、claim 未消费、后续 attempt 和完整历史恢复保持最后归属语义。
- 首次插入 Set 的顺序与旧 flatMap 后逐个筛选并去重的输出顺序相同；仅 transcript 出现的 ID 被排除。消费者 `model-fallback.ts:260` 保留 nano-fallback 前缀过滤与 run.inputs 去重，不变更逻辑 run、状态机、失败重试、粘性或通知。
- 新函数仅在 turn/end 使用；attach 对持久 terminal 的重放仍读完整快照。`inputEvidence` 原实现与 `session.lookup` 投影未修改；没有用当前 turn 前缀替代最终归属。跨包依赖、公开 DSH exports、持久 schema 均未变化。
- 运行代价为 O(E+S+I)，其中 S 包含队列 splice 工作；临时 Set/Map/队列为 O(I+U+Q)，函数返回后无常驻索引。未将此界限错误扩大为整个 ModelFallback 或故障 schedule 的界限。现有 run.inputs.includes 和故障路径查询保留在授权范围内。
- 差分测试覆盖逐前缀语义；计数回归能让旧乘积回放实际变红。RuntimeClient 测试扩展原有文件，新增主模型成功、无备用成功/失败、三 attempt，并对四个前后输入的逻辑 run 归属作隔离断言；保留原有恢复/取消/pre-step 等边界，无重复平行套件。

## Validation evidence reused

核读 `M1-linear-replay/evidence.md` 与 caller 指定的 `/tmp/perf649-environment/{narrow.log,red.log,benchmark.jsonl,build.log}`。20 tests passed、旧算法 5,005,000 visits 超限的 RED、全仓 build 成功与 500/1000/2000 合成实验均有实际日志。2000 历史输入为 20,030,010 → 10,005 次访问，访问减少 99.95%，同机中位耗时改善约 1296x。时延结果仅适用于该合成 fixture，不外推生产占比。

这些日志在代码提交前生成，build 版本戳为基线 `3814a7faae6617df3203fd58382ce7d53419090a`，不能解读为干净基线代码的测试。caller 提供该工作树验证来源；实际实现提交为 `e5a381225`，本轮独立 `git diff e5a381..validated_at` 确认其后仅其他 unit 的设计文档变化，受审源码/测试/benchmark 未改变。未发现需要重复运行已有效覆盖测试的关键缺证；本轮未启动服务或修改实现。

本报告只给代码门禁结论；独立产品 reviewer 的完整栈旅程结论另行记录。
