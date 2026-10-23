# Code Review: perf-651-history-export

## Snapshot and scope

- reviewer: independent agent `/root/static_review`; 未参与受审设计或实现。
- review_mode: `full`
- executed_base: `55376c1112ff870837a6ee65febf52e1f3686a9b`
- validated_at: `b0939cd06` (`b0939cd0658c778671d71b6e4a749201e1a3c5e6`)
- checkout: `/Users/czj/.codex/worktrees/history-export/nano-multiagent`
- branch: `codex/perf-651-history-export`
- reviewed_at: `2026-10-24T01:12:03+08:00`
- 范围：完整 unit diff；唯一产品改动 `packages/dsh-integration/src/history.ts`、新增 `packages/dsh-integration/tests/history-export.test.ts`，并核对相邻真实消费者、DSH 公开契约和 unit 文档。开始时工作区干净。

## Verdict

**Pass — no surviving findings.** 未发现具有具体可触发场景与后果的正确性缺陷。

```json
[]
```

## Coverage and evidence

1. **实际消费者与发布边界。** `packages/dsh-integration/src/index.ts:355-358` 在 trusted binding 校验后调用 `history.path`；`packages/personal-assistant/src/history.ts:152-175` 将返回路径放入用户稍后发送的提炼 prompt，Skill 再读取该 JSONL。`history.ts:311-320,458-460` 每次显式导出完整序列化 header 和事件，再 rename 发布；普通 turn/end 不修改已发布原始文件。因此延迟读取可取得完整旧快照或完整新快照，不暴露原始文件的追加尾行。没有发现绕过 RPC 依赖原始文件自动更新的另一产品消费者。
2. **增量正确性与工作量。** `history.ts:290-310,322-364` 将事件水位和已写字节绑定到 live Session 对象，先校验可读文件长度，正常轮次只投影尾段；raw 全量读取仍仅把水位后的事件追加到可读副本。首次、缺失/长度不符和失败后使用完整原子重建。文本、来源、真人 envelope 过滤和图片占位转换与基线相同。没有持久缓存或正文缓存。
3. **队列与失败恢复。** `history.ts:399-435` 同一 id 串行，使用 pending/raw/rebuild 合并积压；循环清空本轮意图后才 await，期间到来的请求留待下一轮。失败且有新请求时保留尚未兑现的 raw 意图并强制重建，失败且无新请求时拒绝；不同 id 各自执行。`history.ts:365-369` 清除可能部分写入的水位，后续请求重新从 DSH 事实重建。`path` 先 await 队列，错误不能转换为旧路径成功。
4. **持久屏障、冷读和生命周期。** `history.ts:372-397` 在 flush 前捕获上界，snapshot 以此为半开区间终点。核对锁定 `@deepseek-ai/dsh-session/lib/index.js:1367-1382,1820-1855`：seq 是日志长度、snapshot 保持固定前缀，flush 等待所有 durability listeners 并传播失败。query 返回 live 时重新取 Session 并执行同一屏障；prepared 租约仅用于冷恢复，不向未来 live Session 传递游标。锁定 `dsh-session-query/README.md:101-110` 和实现的 source/租约分支支持该判断。
5. **fork、启动和停机真实接线。** `history.ts:205-279` 保留原生 fork 与持久化流程，fork 返回前等可读输出；原始文件由下一次显式请求完整发布。`index.ts:271` 在 accepting 前恢复，`index.ts:587-601` 在输入/Agent 停止后 drain；`recoverExports` 与 turn/end 共用队列，避免两条独立写路径。未改 RPC schema、PA 编排、配置快照或 DSH fork 事实。
6. **永久测试与可信结果复用。** 复用 caller 提供的 7 个导出测试通过、既有 DSH history 与 PA history 共 3 个测试通过；对应命令为 `pnpm exec vitest run packages/dsh-integration/tests/history-export.test.ts` 及 `pnpm exec vitest run packages/dsh-integration/tests/history.test.ts packages/personal-assistant/tests/history.test.ts`，Node 24.22.1。独立核对 `git diff 6fe274eb6..b0939cd06 -- packages/dsh-integration/src/history.ts packages/dsh-integration/tests/history-export.test.ts` 为空，受测实现与固定版本一致。新测试使用真实文件结果和公开 persistence/事件 seam 覆盖忙队列、跨会话、固定切面、部分 append、原始发布失败、缺失副本、冷恢复及 observe 转 live；旧测试保留真实 DSH fork/compaction/restart 接线与提炼编排，未重复建立高层场景。
7. **性能与范围。** 复用 [M1 benchmark](M1-export/evidence/benchmark.md)：顺序 20 轮写入量下降 99.989%，原始事件序列化从 41,650 降为 0；突发 20 个请求只产生 2 次可读写入，最终文件行数与基线相同。含末尾完整显式原始快照的总 payload 下降 97.552%。该证据只支持合成 workload 的逻辑 payload/序列化工作量，不代表设备物理 I/O 或生产时延。

本轮没有修改源码、测试或设计，没有重复全量 CI、启动服务、外发消息或派额外子任务；无具体未证实候选需要追加复现。全量 CI 与独立产品验收由 orchestrator 分别收口。
