# Verification Report: refactor-653-remove-chat-history-copy

> Validation snapshot: `c097a63219d5d303526c2ede583df39b6f81ff9d → 72b2ddb001792f1862764b51ba0d68f5179c61c0`

## Metadata

- reviewer: independent agent `/root/static_review`，未参与受审设计或实现。
- review_round: `1`
- verification_mode: `full` + `corrected-delta`
- executed_base: `c097a63219d5d303526c2ede583df39b6f81ff9d`
- validated_at: `72b2ddb001792f1862764b51ba0d68f5179c61c0`
- checkout / branch: `/Users/czj/.codex/worktrees/remove-chat-history-copy/nano-multiagent` / `codex/refactor-653-remove-chat-history-copy`
- verified_at: `2026-10-25T00:40:57+08:00`
- requires_full_verification: `false`
- canonical_merge_status: `pending`（caller 已明确 delta 尚待归并）

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 单 milestone 的实现范围已覆盖；首文档 2/2 场景、导出 delta 5/5 场景有实现与适用回归证据 |
| Correctness | 无副本写入/旧文件保留、原生历史/fork、显式原始完整快照与失败重试一致 |
| Coherence | Followed；符合 Gate 2 Approved design 与 integration 职责边界 |

**Pass — 0 CRITICAL / 0 WARNING / 0 SUGGESTION。** 实现与 active spec/design 一致；corrected-delta outcome: **aligned**。本报告不表示 canonical 已归并、产品 reviewer 已验收或尚在主 Agent 执行的全量 CI 已通过；这些是交付收尾独立步骤。

## Completeness

- **M1 实现 1/1 覆盖。** 自动 turn/end、fork 后派生输出和 initialize 的 recoverExports 触发均删除；移除可读转换、游标/文件长度校验、append/rebuild 与无用模式标志，只保留显式原始导出队列。配置快照、fork 账本、原生历史和公开 RPC 不变。
- **回归策略可复查。** [M1-remove/progress.md](M1-remove/progress.md) 明确 history-export/history rewrite-merge、native-human-source 删除退役断言、PA history keep；没有机械新增测试文件。先取得“普通轮次应零写入、实际 82 字节”的旧实现红测，再验证修改后通过。新测试从文件/RPC/persistence seam 观察行为，不检查私有水位或 Map。
- **直接结果。** 独立读取 caller 指定 `/tmp/refactor-653-export-test.log`（Vitest 4.1.11，00:39:41，1 文件/7 passed）和 `/tmp/refactor-653-native-test.log`（00:39:32，3 文件/6 passed），与 M1 记录及派发一致。命令分别为 `pnpm exec vitest run packages/dsh-integration/tests/history-export.test.ts`、`pnpm exec vitest run packages/dsh-integration/tests/history.test.ts packages/dsh-integration/tests/native-human-source.test.ts packages/personal-assistant/tests/history.test.ts --maxWorkers=1`；Node 24.22.1，独立临时 home/workspace，无生产连接。最终队列释放简化后低层再次通过；真实 subprocess 结果保护 fork/原生恢复/来源接线，未将其冒称真模型或 UI 验收。
- **尚待 caller 收口的独立步骤。** M1 的本地全量 CI 与产品 reviewer 场景结论不由本静态 verifier 代签；canonical 归并在本次固定版本后执行。本报告核对实现和已有证据，不将这些 pending 步骤记录为已完成。
- **Prototype / Reference：N/A。** 无前端或视觉变更。

## Correctness

| Requirement / Scenario | 实现位置 | 测试/直接证据 | 状态 |
|---|---|---|---|
| 首文档：普通聊天及重启，原生历史继续且不生成副本/旧文件不变 | `history.ts:93-102,263-300`，`index.ts:283-287` 删除 recover | 低层 `history-export.test.ts:78-93,151-160`；真实 `history.test.ts:188-217` 重启前预置旧文件，启动及源/分支继续后旧字节不变、缺少的分支副本仍不存在 | covered |
| 首文档：fork 后继续并导出，继承前缀且不混入源分支点后历史 | `history.ts:179-261` 保留原生 fork/配置；`:263-285` 全事件原始导出 | `history.test.ts:138-217` 真实 fork、配置继承/独立增长，raw 包含 one/fork-only、不含 after-point；重启继续及操作幂等 | covered |
| delta:59-61 连续轮次显式导出完整、不重复、无副本副作用 | `history.ts:263-285,339-341` | `history-export.test.ts:78-93` header 与全部事件相等、显式请求后副本仍 ENOENT | covered |
| delta:63-65 延迟读取完整原始快照 | `history.ts:272-275` 完整临时写后 rename，无普通轮次写路径 | `history-export.test.ts:85-92,134-148` 后续轮次原字节不变、显式请求更新，失败保留旧完整文件；原子发布静态核对 | covered |
| delta:67-69 分支自己的完整历史 | `history.ts:186-261,263-300` | 真实 history fork/raw/重启回归 | covered |
| delta:71-73 原始发布失败后显式重试 | `history.ts:274-275,302-341` | `history-export.test.ts:134-148,163-185` 失败拒绝且旧字节保留、普通轮次不重试、显式请求重试/合并；stop 等待进行中任务 | covered |
| delta:75-77 重启不维护旧可读副本 | `index.ts:283-287`，源码已无 chat_history/recoverExports | 真实 history 重启后旧文件字节与缺少副本断言；低层冷 observation 导出仍不碰旧文件 | covered |
| delta 真人 envelope 剩余 8 个 Scenario 不变 | 删除的是可读投影，未改 PA envelope、submit 或原生来源逻辑 | 对比 current/delta：仅删副本正文片段和 1 个专属 Scenario；native-human-source 保留原生来源、权限与工具行为断言，3 文件/6 passed | covered |

## Coherence

| design 决策 | 遵守? | 证据 |
|---|---|---|
| 完全移除 workspace 派生副本，包括显式导出副作用 | 是 | history 全模块无 chat_history、append/stat/水位；queueExport 仅 path 调用 |
| 保留旧文件，不执行迁移/删除 | 是 | 产品改动没有读取、删除、重写该目录的分支；真实回归验证旧字节不变 |
| 保留完整显式原始 JSONL、原子发布和延迟消费 | 是 | `history.ts:263-300,339-341`；PA `src/history.ts:152-175` 消费者未改 |
| live 捕获 seq 后 flush；prepared/cold→live 合法持久边界 | 是 | `history.ts:277-300`；锁定 DSH README 的半开区间、flush、source 契约；低层 `:120-131,188-200` |
| 显式队列串行化并发，后续显式请求可重试，stop drain | 是 | `history.ts:302-346`；低层并发/跨会话/失败期间新请求与 stop 场景 |
| 不新增模块/开关/兼容层，不改 DSH/原生存储/第二套循环 | 是 | 唯一产品修改为 history 减法与 index 删除一行；依赖与 RPC schema 无变化 |
| 同步当前说明，历史归档保留 | 是（canonical 待 caller 归并） | 两处 nanoassistant-docs、operations 适用性/验收修正；archive 未改；active delta 明确 MODIFIED/REMOVED |

按 session id 的任务在 finally 完成后移除，未在 Map 中长期保留已完成 Promise。没有正文缓存、水位兼容或无消费者的恢复路径。configuration/attach/fork 元数据的权威仍是原生历史与原有 Nano domain，符合 `SPEC.md` 的 integration 职责和 DSH 公开 exports 边界。

### Prototype / Reference Contract

N/A。

## Issues

- CRITICAL: None。
- WARNING: None。
- SUGGESTION: None。

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| MODIFIED 真人 envelope Requirement：删除可读副本正文承诺和专属 Scenario | 不再生成副本；PA envelope/原生来源逻辑未修改 | Python 逐文比较：current 去掉对应 1 段文字与 1 个 Scenario 后与 delta 完全一致；Scenario 9→8；既有来源回归保留 | aligned |
| MODIFIED 原生历史导出 Requirement：仅显式 raw、不自动输出、不碰旧文件 | `history.ts:93-102,261-346`；`index.ts:283-287` | 普通轮次零写入、显式后无副本、旧字节不变，低层及真实 history 回归 | aligned |
| 显式完整、不重复、延迟原子读取、fork 前缀 | `history.ts:263-300,302-341` | 低层 header/全部事件、固定切面、并发与真实 fork/raw | aligned |
| 失败后显式重试、重启不维护副本 | 不再有自动触发/recover；发布失败抛出且 rename 保留旧文件 | 低层失败/显式重试/冷观察与真实重启旧字节保护 | aligned |
| REMOVED PA 在 workspace 产品目录保留可读聊天副本 | 原写入、投影、恢复触发全部删除 | 新保护“缺失仍缺失，旧字节不变”；退役投影测试已删除或改写 | aligned |

### Uncovered Observable Behavior

None。移除启动派生扫描、fork 后可读写入等待与普通轮次自动重试均为“不再维护副本/不自动导出”的实现效果，delta:57、75-77 已覆盖；显式 raw 冷读、原生配置和 fork 语义未新增偏离。

Outcome: **aligned**（delta 与固定版本实现对齐）。canonical 尚未归并：交付前应在 `docs/specs/gateway/routing-delivery.md` 应用两项 MODIFIED 与一项 REMOVED，并同步 `docs/specs/gateway/spec.md:21` 的摘要/计数（23→22）。这属于已知 orchestrator 收尾，不是建议改 spec 适配错误实现；本报告不声称 canonical 已更新。

本轮未修改实现/测试/配置/设计，不运行全量 CI、不启动服务或额外子任务。report_commit: N/A，按派发由主 Agent 集中提交。
