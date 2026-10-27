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

## Round 2 — targeted-closure

- verifier: `/root/static_review`，沿用独立身份，仅核待补证据与版本适用性。
- verified_at: `2026-10-27T12:25:00+08:00`（分钟级）。
- verification_mode: `targeted-closure`。
- executed_base retained: `a78e9498560f6943e934bc29a68e0ac9918270f1`。
- implementation validated_at retained: `25c6d866fb2423fdb0e2d941deabe48a33dd7f76`。
- final-sync snapshot: `54b1214c8d52dc1645df3b526756b9b2d2353a2a`；effective_base: `69d01e4557bcc87a5f7194dcb947c7473ead20d9`。
- evidence commit: `4a8734d02bf48ab1201957cd4428caaf50dad328`，仅新增本 unit 的 acceptance/validation；不是新的运行产品版本。
- final effective_base: `1e2b6dbf6d1b2590a9cee7a6d09171852814ca41`；effective_through: `f907e2978fd53c7d0e0f6663bc51110e19629ce1`。
- focus: Round 1 Pending delivery evidence 两项；无历史实现 finding。
- requires_full_verification: `false`。

### Verdict

**Pass — 0 CRITICAL / 0 WARNING / 0 SUGGESTION。All local checks passed. Ready for PR。** M1 的实现、性能、自动回归与产品验收证据已齐。远端 CI 在 PR 后按工作流执行，仍由交付主流程跟进；本结论不表示远端 CI 已通过或已部署。

### Version and retained coverage

独立执行 `git diff --exit-code 25c6d866f..54b1214c8 -- apps packages src tests scripts pnpm-lock.yaml` 无差异；完整 changed paths 为 feat-665 原始外部附件失效链接说明、main 新增 feat-667 文档、本 unit code-review/verification。54b → 4a873 仅 acceptance/validation。因此 Round 1 的实现正确性、架构/权限、设计一致性、性能实验与 no-spec-delta 结论 retained；没有需要重新全量验证的产品 delta。

最后同步补核：4a873 → f907 仅新增feat-667 design、design-review、delta-spec、M1骨架4份文档；再次比较25c6 → f907的产品、测试、构建路径无差异。主分支文档推进未使本unit证据失效，effective_base/through更新如上，实际validated_at/executed_base不变。

### Evidence closure

| Round 1 待补项 | 已核实证据 | 裁决 |
|---|---|---|
| 真实普通 single_thread 长回复渐进、完整、有序 | `acceptance.md` Round 3；本地原始 `responses-events.jsonl`、`responses-summary.json`、`messages-c_1dbq8zsh.json`。独立重新计算消息 `4cf11105b8ba46919c69762930dd8685` 有 270 个唯一 message.delta，接收观察跨度53.514秒，1,868字；拼接严格等于completed及HTTP历史，01–50顺序完整且各一次；最后delta先于completed | closed |
| 群聊/显式发送、watchdog、contacts 的真实验收 | 独立 reviewer Round1 四项 pass，Round3明确 retained；普通群聊0草稿delta且最终完整，Global显式一次且无哨兵；真实timer保留正文并正确失败、活跃249秒回复不误杀；contacts静态分页50/50/16与116详情一致、Unicode110项无重漏、私人/停用对象列表隐藏且详情404 | closed |
| 完整后端与适用本地检查 | `M1-hot-paths/evidence/validation.md`；原始 `/tmp/perf-666-tests-rerun.log` 核实142files/766tests通过、173.58s；前端日志108files/1031tests通过，Python日志70passed/32deselected；build-final日志确认构建25c6候选，typecheck日志通过；复用主流程check:ios-runtime、ruff及docs-check通过记录 | closed |

Round1仅一次全文delta和Round2模型402余额不足的失败历史保留；Round3使用同Sol的既有Responses流式路径，经正常隔离产品配置入口准备，不改变产品/代理实现，也没有通过改低验收标准关闭问题。本次原始事件能证明渐进交付和最终一致性，不外推为生产RTT、吞吐或所有provider均渐进。

首次默认并发后端全量出现workspace-tools90s超时（其余765tests通过），独立读取原始失败日志；同一测试未改代码/超时，单独35.31s通过，限制4workers的全量766tests通过。该证据足以收口本地测试门禁；资源竞争仍为假设，未称已证明根因，也未隐去首次失败。

### Final reconciliation and handoff

**no spec delta retained。** 无新增对外行为或权限/协议变化，新增证据证明原不变性；不需要 current spec 归并。唯一M1的技术与五个产品Scenario均有直接或可信独立证据，无未闭实现/设计/验收问题。

本 verifier 未启动服务或另建现场；主流程报告已执行e2e-down且Node/DSH进程退出，由主流程保存清理事实。若下一步仅archive移动、对应文档链接修正、收尾记录与远端CI状态追加，本轮结论可retained；交付者应核对实际diff无产品变更。源码、权限、协议、测试或运行前置若再改动，须按其影响作定向或完整复验。
