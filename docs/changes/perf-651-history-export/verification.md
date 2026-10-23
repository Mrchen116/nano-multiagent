# Verification Report: perf-651-history-export

> Validation snapshot: `55376c1112ff870837a6ee65febf52e1f3686a9b → b0939cd06`

## Metadata

- unit_id: `perf-651-history-export`
- review_round: `1`
- verification_mode: `full` + `corrected-delta`
- executed_base: `55376c1112ff870837a6ee65febf52e1f3686a9b`
- validated_at: `b0939cd06` (`b0939cd0658c778671d71b6e4a749201e1a3c5e6`)
- reviewer: independent agent `/root/static_review`; 未参与受审实现。
- checkout / branch: `/Users/czj/.codex/worktrees/history-export/nano-multiagent` / `codex/perf-651-history-export`
- verified_at: `2026-10-24T01:12:03+08:00`
- requires_full_verification: `false`

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 实施退出标准 1/1；首文档 3/3 场景、delta 4/4 场景有实现与适用证据 |
| Correctness | 完整投影、持久上界、队列与故障恢复、fork/冷读契约一致 |
| Coherence | Followed；符合 Round 3 Approved design 与仓库架构边界 |

**Pass — 0 CRITICAL / 0 WARNING / 0 SUGGESTION.** 实现与本 unit spec/design 一致，可进入其余交付门禁。本报告不代替独立产品 reviewer 的场景判定或全量 CI。

## Evidence baseline

- 可信窄测试由 caller 提供并复用：Node 24.22.1，`pnpm exec vitest run packages/dsh-integration/tests/history-export.test.ts`，7 passed；`pnpm exec vitest run packages/dsh-integration/tests/history.test.ts packages/personal-assistant/tests/history.test.ts`，3 passed。实施记录见 [M1-export/progress.md](M1-export/progress.md)。本 reviewer 未重复执行这些测试。
- 独立核对 `git diff 6fe274eb6..b0939cd06 -- packages/dsh-integration/src/history.ts packages/dsh-integration/tests/history-export.test.ts` 无差异，因此 M1 记录的受测实现适用于固定 validated_at。既有 history 测试在 unit diff 中未改。
- [M1-export/evidence/benchmark.md](M1-export/evidence/benchmark.md) 含 claim、基线、fixture、结果、命令与限制：20 个顺序新增轮次的应用 payload 下降 99.989%，原始事件序列化由 41,650 降为 0；含最终显式快照的全段 payload 下降 97.552%；最终原始/可读文件行数与基线一致。临时脚本已移除，长期保护在新增导出测试。该证据不代表物理 I/O、真模型或生产加速比。
- 只读取证：完整 base..validated_at diff、当前 `SPEC.md` 的职责/公开 exports 约束、`docs/specs/gateway/routing-delivery.md:540-551`、testing/evidence 规范、原始消费者与真实 RPC 接线、锁定 DSH 的 flush/半开区间/source 租约契约。未修改受审代码或设计，未起服务或占用生产现场。

## Completeness

- **M1-export 1/1 实施完成。** `design.md:69` 的顺序 ≥95% 与突发合并目标由 M1 benchmark 支持；持久上界、同会话并发、跨会话独立、延迟原始读取、失败重建、缺失文件及冷读转 live 由 `history-export.test.ts:83-215` 覆盖。真实 fork/compaction/restart 接线由既有 `history.test.ts:7-240` 及其可信通过结果支持，提炼路径编排由 PA history 测试支持。
- **首文档 3/3 场景有实现。** 连续聊天后的完整副本、fork 继承及独立增长、失败/重启后从原生事实恢复均有映射，见下表。`[reviewer]` 用户场景仍由独立产品 reviewer gate 判定，本报告只核实现和证据一致性。
- **Prototype / Reference：N/A。** 无前端或视觉变更。
- **测试归属符合规范。** 新增文件 216 行，保护增量文件 I/O、并发和持久边界的新失败原因；保留原有真实运行时/PA 接线测试。实施记录明确保留/新增分工，不按测试文件数凑覆盖。

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 / evidence | 状态 |
|---|---|---|---|
| motivation:27-31 完整历史继续可供阅读和提炼 | `history.ts:309-364,458-460`；`index.ts:355-358`；`personal-assistant/src/history.ts:152-175` | 导出测试 `:83-100` 全量事件与可读行；既有 history `:188-203` 原始/可读与 envelope；PA history 的路径 prompt 编排 | covered |
| motivation:33-37 fork 保留继承边界且独立增长 | `history.ts:205-279` 保留原生 fork；新 Session 无水位首次全量；`writeLive:375-381` 不跳过继承前缀 | 既有 history `:138-203` 排除 after-point、分支继续/源独立、原始/可读导出；`:204-225` 重启后独立配置与继续执行 | covered |
| motivation:39-43 恢复不依赖派生副本 | `history.ts:299-307,354-369,438-449`；`index.ts:271` | 导出测试 `:139-181` 部分 append/原始失败/删除/冷恢复及新 live 接管；既有 history 的真实 restart 接线 | covered |
| delta:9-11 连续轮次导出完整且不重复 | `history.ts:309-364,399-435,458-460` | 导出测试 `:83-136` 对全部事件、消息和固定持久上界断言；M1 最终 2172/82 行与基线相同 | covered |
| delta:13-15 延迟提炼读取完整原始快照 | `history.ts:311-320` 临时写入后 rename；普通轮次 raw=false | 导出测试 `:89-100` 后续聊天后原始内容保持完整旧值，再显式请求更新；`:147-167` 发布失败保留完整旧文件；原子发布机制静态核对 | covered |
| delta:17-19 分支导出包含自己的完整历史 | `history.ts:262-279,309-324,375-381` | 既有真实 history `:138-203`；不改原生 prefix/fork 机制 | covered |
| delta:21-23 派生写入失败后重建 | `history.ts:365-369,419-425,438-449,458-460` | 导出测试 `:139-199` 验证错误拒绝、旧 raw 保留、可读尾行修复、缺失文件、冷恢复及失败期间新增请求保留 raw 意图 | covered |

原有 `docs/specs/gateway/routing-delivery.md:542` 仍描述可读副本为派生文件，不作为恢复事实。其 conversation-id 命名与现有 session-id 的漂移早于本 unit，design:47 已披露；本变更保持现有实际命名，没有借优化引入迁移。图片占位与来源转换代码从基线原样保留，raw 保留全部事件与版本头。

## Coherence

| design 决策 | 遵守? | 代码与契约证据 |
|---|---|---|
| :31 仅显式请求完整原始快照，原子发布 | 是 | `history.ts:111-114,311-320,458-460`；PA 实际只经 session.export 获取提炼路径 |
| :32 WeakMap 生命周期水位、可读增量与重建 | 是 | `history.ts:99-102,290-310,354-369`；prepared 调用不传 session，不向未来 live 移交游标 |
| :33 单会话合并 pending/raw/rebuild、跨会话独立、失败意图不丢 | 是 | `history.ts:399-435`；新增测试忙队列、跨会话及失败期间请求覆盖 |
| :34 同队列恢复、fork 等待、stop drain | 是 | `history.ts:279,438-465`；`index.ts:271,587-601` 先阻止/结束输入再 drain |
| :39 固定上界与 cold→live 屏障 | 是 | `history.ts:375-396`；锁定 DSH seq/flush/source 公开契约；新增测试 `:124-136,202-215` |
| :35 无第二份事实源/全量缓存，普通更新随新增量 | 是 | 只保存 offset/bytes 与队列标志；使用原生 DSH 事件；未更改依赖、runtime、PA/RPC schema |
| :41-43 失败不返回成功，完整原始文件与热可读尾行边界区分 | 是 | `history.ts:319-320,355-369,458-460`；两份派生文件不承诺跨文件事务，符合明确设计 |

新增 `SessionLogOffset` 来自已声明的 `@deepseek-ai/dsh-session` 公开 export，仅调整既有 snapshotEvents 调用区间；没有 private import、DSH patch、新增 Agent Loop 或跨包反向依赖，符合 `SPEC.md` 的 integration 职责。

### Prototype / Reference Contract

N/A。

## Issues

### CRITICAL

None。

### WARNING

None。

### SUGGESTION

None。

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `specs/gateway/routing-delivery.md:7` 显式原始快照、自动可读副本、schema/来源/图片/派生边界 | `history.ts:111-114,309-364,438-460`，转换保留原表达式 | 导出测试暖轮/冷恢复，既有 DSH/PA history；转换代码基线比对 | aligned |
| :9-11 完成队列后完整、不重复切面 | `history.ts:375-381,399-435,458-460` | 导出测试 `:83-136`；M1 完整输出行数对比 | aligned |
| :13-15 源继续聊天或再次导出时延迟读完整 raw | `history.ts:311-320` 完整临时写 + 原子替换，turn/end 不写 raw | 导出测试暖轮保留旧 raw、再次请求全量；失败发布保留旧 raw；rename 发布静态核对 | aligned |
| :17-19 fork 继承与独立增长 | `history.ts:205-279,309-324` | 既有真实 history `:138-203` | aligned |
| :21-23 失败不伪报成功、下次与启动重建 | `history.ts:365-369,419-425,438-460` | 导出测试 `:139-215` | aligned |

### Uncovered Observable Behavior

None。完整 diff 的新增对外行为是原始文件从自动更新改为显式快照，以及可读副本从原子完整替换改为可见追加尾行；delta:7、:13-15 已明确二者。冷读转 live、生命周期水位和合并队列是兑现上述契约的机制，没有额外 schema、命名、权限、RPC 或客户端行为变更。

Outcome: **aligned**。
