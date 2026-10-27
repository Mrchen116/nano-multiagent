# perf-650 Code Review

## Round 1

- reviewer: `/root/usage_static_review`，未参与受审实现；按明确派发兼任独立 verifier，分别保留报告。
- review_mode: `full`
- branch / workspace: `unit/perf-650`；`/Users/czj/.codex/worktrees/unit-perf-650/nano-multiagent`
- executed_base: `40deea7f19794b73614e56c339fd02a88dd1ae7c`
- validated_at: `cc091e4b9a396e87a659fedadb296c5a924d80e4`
- diff_range: `40deea7f19794b73614e56c339fd02a88dd1ae7c...cc091e4b9a396e87a659fedadb296c5a924d80e4`
- 派发时冻结版本为 `63e9c73b7f5cd352dfa4a28f6b910fd2f3b27483`；caller 明确追加 `cc091e4`，独立确认唯一 delta 为 `UsageReader.update` 的 `: Promise<void>` 返回类型注解，不改变运行行为。
- effective_base / effective_through: 留给收尾 owner 在后续同步时判断；本报告只声明上述实际执行版本。

## Conclusion

**通过，无存活 finding。**

```json
[]
```

## Coverage and evidence

- 完整核对 unit diff 的 integration reader/RPC、PA drain/outbox、product-contracts 类型和测试，追踪既有 Node 初始化/重连 recover、NodeStore 用量去重、IM `node.report` 的 `(node_id, run_id)` 持久 receipt。`input-evidence.ts`、`model-fallback.ts`、SingleThread 和 session.descendants 未改，未扩张用户授权范围。
- `packages/dsh-integration/src/usage.ts:29` 在首次 recovery await 前订阅事件；根读取 `tail` 串行；每会话 seq 上界、pending 与 unfinished turn 保留初始化和 flush 期间的新事实。读取公开锁定 DSH 实现，确认 `Session.append` 先写日志后同步发布 event，`seq` 是下一事件位置，`isOwnSeq` 排除 fork inherited prefix；flush 等待所有持久监听器且 detached 对象拒绝；observation 提供 live/prepared 和不可变 cursor。因此 fixture 所用关键语义与实际能力一致。
- `usage.ts:109` 在 live flush 成功后只消费事先捕获 cut；失败不推进，卸载改用 prepared observation 并拒绝未达到 queued seq 的持久 cut；成功消费后只保留新增 pending，不重复发布完成轮次。运行中新 child 经 catalog/parent 链接入，`index.ts:192` 以已发现 owner 映射补全已卸载祖先的 root 通知；可信 binding 校验仍在 `index.ts:370`。
- `packages/personal-assistant/src/usage.ts:45` 仅在所有同步 saveUsage 成功后推进内存 cursor；部分保存可安全按稳定 run id 重放。ACK 失败不删除 outbox，ACK 等待期间新 dirty roots 在同一 drain 再消费；drain 最后检查和 running 清理在同一 continuation，消除退出窗口。NodeStore 新 partial index 支持原 pending 查询，历史 acknowledged 行继续承担去重。
- 复用并核对 M1 progress 的真实 readUsage 400 child benchmark 原始 jsonl、两文件 10 passed 窄测试、真实锁定 DSH workflow-native 1 passed。读取 `/tmp/nano-perf650-evidence/native.log`；核对 `/tmp/nano-perf650-evidence/final-build.log` 的 installer candidate 为 `cc091e4` 且 `pnpm build` 完成。此前 build 的 TS7023 已由该单行注解解决，不作为存活问题。
- 真实函数测量：冷恢复 401 observations / 200,500 events / 40,100 reports / 68.712 ms；不变热读 0 observations / 0 catalog / 0 events / 0 reports / 0.049 ms；单 child 新 turn 0 observations / 0 catalog / 1 report / 15 tokens / 0.069 ms。该内存 fixture 只证明处理量和该样本函数时间，不推断生产 I/O 或端到端速度。冷恢复比基线 25.222 ms 慢，仍为允许的首次线性重建；紧凑 reports 内存仍随完成轮次数增长。

## Boundary

本次只写本报告和 `verification.md`，未改源码、测试或设计，未提交。没有用静态检查替代独立产品旅程验收；最终全 CI 由 caller 执行，未机械重复。无待追加核验的高风险或争议候选。
