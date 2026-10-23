# Verification Report: perf-648

> Validation snapshot: `1ef49808ffd2618c275b6e38683f93f74ff8455d → 2c4b06abcad6ab4af35d2fffdf0daeb6ba7788a1`

## Round 1

- reviewer: independent Codex subagent `/root/static_review`，caller 明确派发兼任代码审查与 verifier；未参与实现。
- verification_mode: `full`；review_round: `1`。
- branch / worktree: `unit/perf-648` / `.worktrees/unit-perf-648`。
- requires_full_verification: `false`（本轮已为 full）。
- verdict: **pass，0 CRITICAL / 0 WARNING / 0 SUGGESTION**。
- scope: M1 实现、需求不变性、design 决策、回归证据及 no spec delta 核对；独立产品旅程验收和 required CI 仍由 caller 汇总，不以本报告替代。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 worker 实现与适用回归证据齐全；两个用户 Scenario 有代码/协议级保护，真实产品验收另属 reviewer |
| Correctness | RPC 选择、fallback 终态、证据保护、迁移与 receipt 恢复均 covered |
| Coherence | Followed；保持 PA / integration / Node 边界，无新 runtime API |
| Spec delta | no spec delta，与完整 unit diff 一致 |

实现核对通过。caller 可继续汇总独立产品验收与 required CI 后交付 PR。

## Completeness

- `design.md:67` 唯一 M1 的 worker 退出标准均有直接实现和适用证据：1000+K RPC、fresh evidence、receipt 中断、fallback switching/multiple attempts、取消/未消费、旧库与重启、延迟物理事件保护。
- `motivation.md:30-40` 两个用户不变性 Scenario 对应既有交付路径及回归测试；没有将 mock relay 结果宣称为实际 IM 产品验收。
- 复用 `M1-pending-evidence/progress.md` 及实际读取的 PA171、build、typecheck 日志；增加独立旧库存量行/延迟事件后重开探针和 runtime input-evidence 3 项窄测试。精确命令、输出及构建版本局限见同轮 `code-review.md` Validation。
- Prototype / Reference：N/A；本 unit 没有客户端布局、视觉或交互变更。

## Correctness

| Requirement / Scenario | 实现位置 | 测试/证据 | 状态 |
|---|---|---|---|
| 完成历史补证据后零 lookup；1000 历史 + K 待定仅 K lookup（motivation:26；design:67） | `single-thread.ts:202-208`；`store.ts:203-204` | `input-reconciliation.test.ts:43-76`，171 tests 中通过；benchmark 不作生产延迟承诺 | covered |
| 同一聊天持续回复且历史结果不重复（motivation:30-34） | `single-thread.ts:162-169,211-220,248-310`；稳定 session/operation 身份未改 | 既有 single-thread/store/fallback 测试 keep；新增重开 DB 的完成回复只发一次用例 `input-reconciliation.test.ts:78-116` | covered；真实旅程另验 |
| 备用模型的中间失败不冒充最终完成（motivation:36-40） | `single-thread.ts:204-207,214-225`；runtime `model-fallback.ts:169-179`；`presentation.ts:82-89` | `model-fallback.test.ts:6-129` 保留提示/正文/usage；`input-reconciliation.test.ts:136-160` 覆盖 snapshot running/switching 滞后 | covered |
| 已固定终态且 receipt 未确认，重启只补 receipt（design:33） | `single-thread.ts:218-220,386-391`；store final 与 receipts 分表 | `input-reconciliation.test.ts:78-116`，真实 SQLite、receipt 故障、重开、零 lookup、单次 receipt | covered |
| 缺 pending、仍 pending、未消费不固定；取消未消费可固定（design:31,45,53） | `single-thread.ts:207`；runtime `input-evidence.ts:14-40` | `input-reconciliation.test.ts:60-75`；本轮独立 `input-evidence.test.ts` 3/3 passed | covered |
| 旧数据库不凭已有 terminal 猜完成（motivation:48；design:31,37） | `store.ts:55-61,180,249` | 既有新测试迁移 schema；本轮额外在迁移前插入真实旧行，确认旧 error 保留且仍待查 | covered |
| final 证据不被较晚物理失败覆盖，跨重启保留（design:35） | `store.ts:191-194,225-230` | `input-reconciliation.test.ts:118-134`；本轮探针串联 late events + reopen，terminal=completed、0 待查、2 events | covered |

表中未写包前缀的实现和测试路径均位于 `packages/personal-assistant/src/` 或 `packages/personal-assistant/tests/`；runtime 文件位于 `packages/dsh-integration/src/`。

## Coherence

| design 决策 | 遵守 | 代码证据 |
|---|---|---|
| fresh lookup + accepted/pending/terminal + logical completion；不信旧 terminal | 是 | `single-thread.ts:203-208`；lookup / fallback evidence 真实 handler 已追踪 |
| final 证据与 delivery/receipt 分离 | 是 | `store.ts:191-194`；`single-thread.ts:211-220,386-391` |
| 限制物理事件 writer，保留全部 runtime events | 是 | `store.ts:225-230`；本轮及永久回归证明事件仍完整 |
| additive schema、索引、ID-only 查询，无额外状态机/TTL | 是 | `store.ts:29-34,55-61,203-204` |
| Global 默认 final=false，不扩大范围 | 是 | `global-agent.ts:535`；`store.ts:191`；本轮探针验证默认路径原更新行为 |
| Node 真实使用 SingleThread；仅经 RuntimePort 接触执行层 | 是 | `apps/node/src/main.ts:335-338`；受审产品 diff 不新增 import/依赖/API；符合 `SPEC.md:29-40,56-58` |

### Prototype / Reference Contract

N/A。

## Issues

### CRITICAL

无。

### WARNING

无。

### SUGGESTION

无。

## Spec Reconciliation

**no spec delta**。核对 `design.md:47-49`、完整 5 文件 diff 和 current `docs/specs/gateway/routing-delivery.md`、`agent-capabilities.md`：新增字段和 SQL 筛选只改变内部 RPC 选择；原聊天归属、可见回复、fallback 提示/正文、receipt 与取消规则均保留。未新增外部契约、未修改 runtime 协议，未发现 delta 遗漏的对外行为。

完整 drain 仍读取历史事件并遍历输入；本报告只确认常态逐输入 lookup RPC 随待处理集合收敛，不声称整体 drain 为 O(K)、生产提速比例、服务部署或公网稳定性。

## Handoff

- 本轮仅写 `code-review.md`、`verification.md`，共享现场由 caller 提交；`report_commit: pending caller collection`。
- 没有自建 worktree 或启动服务；探针临时 SQLite 已删除，未修改源码、测试、配置或设计。

## Round 2 — Final Main Sync Delta Verification

> Validation snapshot: `b78b263abc8249617906117f8f19eeb1e825fab3 → 817f92040be5916e5abb42196948c1147009c399`

- reviewer: independent Codex subagent `/root/static_review`；与 R1 相同，未参与实现。
- verification_mode: `delta`；review_round: `2`。
- main_delta: `1ef49808ffd2618c275b6e38683f93f74ff8455d..b78b263abc8249617906117f8f19eeb1e825fab3`；effective / executed_base 为上述 snapshot 左端。
- verdict: **pass，0 CRITICAL / 0 WARNING / 0 SUGGESTION；Round 1 retained**。
- requires_full_verification: `false`。

### Delta Coverage

| main 增量 / 共享面 | 核对结果与证据 | R1 结论 |
|---|---|---|
| perf-648 产品源码和回归测试重放 | `git diff 2c4b06abc..817f92040 --` 两源码/两测试为空；store 与 single-thread blob 相同 | 输入筛选、最终判据、迁移、持久写入、receipt 恢复全部 retained |
| runtime 新 sessionPersistence 注入及 descendants reader | `index.ts:94,384-403` 增量仅新服务依赖和子轨迹读取；`session.lookup:363-367`、`session.observe:377-382` 既有函数体未变 | 权威 fresh lookup、logical modelRuns 语义 retained；启动兼容性由 caller 同版本运行测试补证据 |
| input-evidence / fallback / PA logicalEvents / Node 实际接线 | 四文件 R1→R2 diff 为空，R1 追踪的真实调用链和 logical/physical 区别仍成立 | fallback、延迟物理事件保护及原聊天路径 retained |
| Global root/child drain 分离 | root source checks 仍观察持久证据；`global-agent.ts:535-539` 原输入 lookup writer 仍默认 final=false；新 reader/cache/cursors 不操作 inputs final 字段 | Global 原行为、NodeStore 所有权边界 retained |
| integration package 与 lock | 声明公开 session-persistence 根 export，版本与原 DSH 锁定基线一致；没有跨包 private import | 架构一致性 retained |
| 其它 main 文档、IM UI current spec 小改 | 与 perf-648 两个不变性 Scenario、design、M1 退出标准无交集 | no spec delta retained |

本轮没有新实现或冲突修复，也未发现会使 R1 证据失效的共享语义变化。R1 已在不含 bugfix-647 的原 runtime 上完成，故该 main 增量不是本 unit 成立的前置依赖。无需扩大为全量重新验证。

### Validation / Remaining Caller Gates

- 同步现场 HEAD 与指定 validated_at 一致；检查两快照真实差异，未只依赖“无冲突”说明。完整 unit 范围 `git diff --check` 通过。
- 已读取同版本 final-install 日志，安装/lock 对齐通过；读取时 final-build 仍运行。caller 正在重跑 build/typecheck、受 main 增量影响的 descendants/tool-presentation/global、完整 PA 与 native model-fallback；最终结果由 caller 汇总，不将尚未完成的命令视为通过。
- 本轮 verifier 结论为 delta 的实现/架构核对 pass；保留 R1 已证明的行为与证据范围。最终 PR 交付仍须 caller 完成同版本运行门禁归集。
- no spec delta；没有发现 unit diff 中新增而未归并的对外行为。
- 仅追加本两份报告，不修改 R1 历史，不改源码/配置，不提交；`report_commit: pending caller collection`。
