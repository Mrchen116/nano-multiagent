# Verification Report: perf-666-im-hot-paths

> Validation snapshot: `a78e9498560f6943e934bc29a68e0ac9918270f1 → 25c6d866fb2423fdb0e2d941deabe48a33dd7f76`

## Round 1 — full

- verifier: `/root/static_review`，独立于实现；只写 verification 与明确派发的 code-review 报告。
- executed_base: `a78e9498560f6943e934bc29a68e0ac9918270f1`
- validated_at: `25c6d866fb2423fdb0e2d941deabe48a33dd7f76`
- verified_at: `2026-10-27T12:08:00+08:00`（分钟级）
- verification_mode: `full`，包含 no-spec-delta 核对。
- requires_full_verification: `false`

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 3/3 技术优化已实现；M1 产品验收和完整本地/远端 CI 证据待主流程完成 |
| Correctness | 现有消息、超时、联系人与权限契约 aligned；独立定向回归 25 tests passed |
| Coherence | 4/4 关键设计决定 Followed；no spec delta 成立 |

**实现核对通过，0 CRITICAL / 0 WARNING / 0 SUGGESTION。完整交付结论为 Pending evidence，尚不声明 Ready for PR。** 尚未完成的验收/CI 是退出标准的待补证据，未当作已证实的代码缺陷。

## Completeness

- M1 是单一 milestone；stream batching、server delta 窄投影、watchdog 查询/索引、contacts 定向详情/有界分页全部有实现。
- worker 的缓冲生命周期、失败/ACK loss、完整性与顺序、contacts 分页/搜索/资格、watchdog 判定回归有测试。性能报告与原始脚本/日志匹配，达到 watchdog 50 万历史事件低于基线 20% 的设计目标。
- 复用主流程报告的 `pnpm build`、`pnpm typecheck` 通过结果；本 verifier 未重复全量命令。完整 `pnpm test`、远端 CI、真实 single_thread 私聊/群聊及其余验收由主流程继续收集。
- Prototype / Reference：N/A，无客户端 UI 变化或 must-match 原型。
- 无源码、测试、配置、设计变更；未启动长期服务，无自建现场待清理。

## Correctness

| Requirement / Scenario | 实现位置 | 测试/证据 | 状态 |
|---|---|---|---|
| 长回复渐进、完整、有序、正常完成 | `packages/personal-assistant/src/single-thread.ts:436-496`；原 reconcile:317-350 | model-fallback 慢 ACK/ACK loss 与 final 顺序；合成 relay 性能脚本拼接及最终全文比较 | 实现/自动回归 covered；真实模型验收 pending |
| 群聊与显式回复无草稿/结束哨兵泄漏 | single-thread:437、475-480；原 explicit/group reconcile 路径 | interactive-replies 既有公开 relay 输出断言；原 single-thread/group 保护由主流程窄套件覆盖 | covered；真实群聊验收 pending |
| modelCheck/stop flush，停用丢弃待发文本 | single-thread:55-59、360、445-449、461-496 | model-fallback 的 modelCheck/stop/cancel；PA agent-lifecycle | covered |
| delta 重传幂等且权限不放宽 | `apps/im-server/src/gateway.ts:870-901` | server e2e 重复相同 delta key，消息历史/WS 完成；保留 requireAgent、双 lifecycle、PA 和 s.access 检查 | covered |
| 活跃不误超时，停滞失败且正文保留 | `apps/im-server/src/server.ts:315-340` | watchdog 真 timer + SQLite：最新时间、旧事件后插入、cutoff 边界、无事件、completed、保留已有正文 | covered |
| contacts 搜索/类型/静态分页不重不漏，详情相符 | `apps/im-server/src/contacts.ts:7-87`；messaging:797-807 | contacts HTTP 测试：180 个穿插隐藏候选、两页、Unicode、详情、invalid kind | covered |
| 私人及停用 owner 的 Agent 不可见/不可访问 | contacts:23-44；identity:49-65 | contacts 动态 owner/PA 资格；现有 tenancy 测试由主流程报告通过，代码逐条件对照 | covered |

独立命令与结果见同版本 [code-review.md](code-review.md)：最新三文件 10 tests、既有 server/interactive/lifecycle 三文件 15 tests，均通过；diff whitespace check 通过。

## Coherence

| design 决策 | 遵守? | 代码与证据 |
|---|---|---|
| 每 stream 单一在途，50ms/4096 触发、ACK 后合并、end/stop/modelCheck flush、cancel 丢弃 | 是 | single-thread:55-59、360、436-508；慢 ACK 100 fragments 的实验由 100 次 delta 降为 5 次，最终正文相同 |
| delta 仅窄读身份/权限字段，复用原有权限和原子正文追加 | 是 | gateway:870-901；Messaging.actor 的 sender 推导一致，非 delta 投影未改变 |
| 先 running，再索引取最新事件，保留原超时语义 | 是 | server:322；schema:418-420；EXPLAIN 使用 messages_running / conversation_events_latest；50 万事件 124.024ms → 0.002ms（本次内存实验） |
| contacts 单 ID 详情、有界候选/批量 owner+binding、JS Unicode 搜索 | 是 | contacts:7-87；schema 的 users_owner；PA binding.agent_id 唯一 JOIN；真人详情和首页 SQL 数不随总目录人数增长 |

架构核对：新增模块位于 IM 内部；PA 仍只消费既有 runtime/relay port，无 DSH 导入、运行时补丁、跨包相对依赖或第二 Agent Loop。新增索引由现有 schema 初始化幂等创建，无历史数据格式变化；首次建索引的扫描成本已由 design 明示。本次无部署授权或部署动作。

性能报告采用基线 main `85910853`；已检查其原始源码提取及候选脚本。审查 diff 的 executed_base 是 `a78e94985`，二者用途不同；未把性能基线误写为此次审查起点。实验为本机内存库/模拟 relay，并非生产吞吐、磁盘 IO 或真实模型速度保证。

### Context

复用同版本 code reviewer 的影响评估：宿主 modelCheck 的发布等待改为先 flush，模型输入、工具/Schema、Skill、Memory、history 及注入文本均未改变。未发现实现偏离 Context 设计或新增 Context 接口缺陷；真实 provider 输入/模型消费未单独捕获，不用自动化 stub 证明模型行为。

### Prototype / Reference Contract

N/A。

## Issues

### CRITICAL

无。

### WARNING

无。

### SUGGESTION

无。

## Spec delta reconciliation

**no spec delta。** 已对照 `docs/specs/im/auth-tenancy.md` 的数据面与资源空间约束、`agents-nodes.md:742-755` 的联系人发现/公开资料、`gateway-relay.md:61-78` 的流式幂等、`personal-agent.md` 的 PA 边界，以及完整 unit diff。公开 HTTP/WS 字段、权限、联系人投影、搜索语义、最终正文及超时规则保持；50ms/4096/100 候选是内部触发与批次参数，未成为公开承诺。未发现被 no-spec-delta 漏掉的预期对外行为变化。

## Pending delivery evidence

1. M1 reviewer 的真实 single_thread 长私聊 delta/completed、群聊草稿抑制、显式发送、contacts 与 watchdog 场景验收：主流程正在隔离 daily 真栈执行。
2. 完整本地测试与适用本地 CI、远端 CI：由主流程补结果和版本定位。build/typecheck 已由主流程报告通过。

这些结果到齐后可就证据补齐作定向 closure；若源码改变，需按实际 delta 决定复验范围。本轮不预设未来 CI 或验收通过。
