# Verification Report: refactor-682-agent-catalog-lifecycle

> Validation snapshot: `99354a6a1 → 0812c67efe12174c429c372103fb8842891eed64`

## Round 1

- unit_id: `refactor-682-agent-catalog-lifecycle`
- review_round: 1
- verification_mode: `full`
- branch / verify_worktree_dir: `codex/agent-catalog-lifecycle` / `/Users/czj/.codex/worktrees/agent-catalog-lifecycle/nano-multiagent`
- validated_at: `0812c67efe12174c429c372103fb8842891eed64`
- executed_base: `99354a6a1`
- reviewer: `/root/catalog_static_review`，独立于实现；2026-10-31。
- verdict: **NOT PASS — 2 CRITICAL / 1 WARNING**。
- requires_full_verification: false。已完成 full 静态核对，后续按本报告 findings 与证据缺口定向闭环；若补丁扩大共享边界，应由 caller 重新判断范围。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 已有主体实现，退出标准未全部完成 |
| Correctness | IM/RPC/Node/Context 关键机制已有窄覆盖；两个进程生命周期问题须修复 |
| Coherence | 总体遵守设计与包边界；startup cleanup 隔离和整个进程组释放不符 |

当前验证不放行 PR。caller 正在补充的测试未计为通过，也不要求重复执行已有有效验证。

## Completeness

- Milestone: M1 `design.md:117` 尚未完成；缺口见 V1-W1。
- Spec: IM modified Requirement 及其原有候选字段/来源/选择语义有实现；新增连续读取、缓存与恢复分支有实现。Gateway 临时资源隔离实现存在 V1-C1/V1-C2。
- Prototype / Reference: N/A，用户明确纯后端，无 UI must-match。
- 当前声明无部署/发布；历史 preview 一次性部署只受另行授权约束，审查未操作生产。

## Correctness

| Requirement / Scenario | 实现位置 | 测试/证据 | 状态 |
|---|---|---|---|
| IM 同 owner/绑定/连接/workspace/profile 的五分钟候选复用与 capture time | `apps/im-server/src/catalog-reads.ts:44-102` | catalog-reads TTL/scope/capacity 测试；IM 日志 78 passed | covered |
| 连续/并发 settings 读，不持有配置写锁 | `apps/im-server/src/control-routes.ts:337-365` | 30 concurrent、写锁隔离、pending background recovery 测试 | covered |
| 失败降级、权限/连接/profile/invalidation 迟到 fence | `control-routes.ts:353-366`、`catalog-reads.ts:35-40,85-97` | IM settings invalidation/snapshot、RPC timeout/disconnect | covered，完整两层交错证据待补 |
| node/agent/settings 候选同源，安全投影/模型与来源 | `control-routes.ts:200-228,500-520`、`apps/node/src/capability-requests.ts:37-77` | 既有 control/capabilities/native fixtures；Node 真实同源验收待补 | partially evidenced |
| 临时 catalog/preview/prepare 不写持久聊天 home | `packages/dsh-integration/src/index.ts:379-430,634-642`、`configuration-inspector.ts:160-190` | capabilities 3 catalog 后持久 Sessions 无 preview；inspector 每次 home 回收 | covered，100 次/soak 待补 |
| 取消/超时/并发超限后释放且聊天不重启 | `configuration-inspector.ts:83-128,147-205`、`apps/node/src/capability-requests.ts:24-85` | 30 waiter、单取消、死循环 timeout 后恢复且聊天 PID 不变、generation、owner SIGKILL recovery；native 5 passed | V1-C2，其他分支 covered |
| 未知 orphan 身份保留且只拒绝新临时检查 | `apps/node/src/main.ts:49-50`、`configuration-inspector.ts:208-230` | 现有 mismatch 测试确认 initialize rejects；Node 顶层错误传播 | V1-C1 |
| 保存重新验证真实候选、不扩大白名单 | `packages/dsh-integration/src/index.ts:634-650` | native capabilities empty/subset/Feature/撤销、workspace actual dispatch；无 TTL 复用 | covered；完整保真对照待补 |
| 独立插件/任务/统计/渠道分区 | `control-routes.ts` 原 section 分区与路由保留 | settings/control 既有 tests；真实 HTTP 验收 caller 正在补 | partially evidenced |

## Coherence

| design 决策 | 遵守? | 证据 |
|---|---|---|
| 保留现有 UI/API 与 last-known/只读规则 | 是 | 无 UI diff；settings 输出沿用现有字段与快照投影 |
| IM 仅内存候选，配置操作不靠缓存授权 | 是 | `catalog-reads.ts`、`index.ts:634-650` |
| Node/DSH 公开 client 边界与独立官方 worker | 是 | `main.ts:18,49`、`client.ts:58-65` |
| 2-worker single-flight、generation、独立 waiter | 是 | `configuration-inspector.ts:77-134`；跨层全链测试待补 |
| deadline/kill/reclaim 不影响聊天 | 部分 | 临时 timeout 正常；V1-C1、V1-C2 不满足 |
| 全 preview/prepare 调用者保真 | 实现同源，证据未齐 | `index.ts:379-430,457-460,634-650`；详见 V1-W1 |
| 精确历史 preview 迁移，仅副本验收 | 方案符合，证据待补 | `deployment-prompt.md:5-13` |

### Prototype / Reference Contract

N/A。未引入前端原型或视觉参考。

## Issues

### CRITICAL

- **V1-C1 / code-review F1 — inspector orphan 错误阻断 Node 启动。** 契约：Gateway delta“临时能力检查不污染或阻塞持久执行”、design 决策 3 的未知身份保留/拒绝新检查和聊天隔离。实际：`apps/node/src/main.ts:50` 不处理 `recover()` 拒绝；Node 尚未创建聊天运行时/relay 即失败。保留可疑目录与 cleanup_error，同时让 Node 正常启动，仅禁止 inspection；从 Node 启动 seam 验证身份不符/无法清理不会阻断聊天恢复。证据、精确触发见 code-review.md F1。
- **V1-C2 / code-review F2 — 以 leader 退出误作进程组释放。** 契约：design 决策 3 与 Node/integration 段要求终止进程组、确认退出再删 home；Gateway delta 要求成功/失败/取消释放临时执行资源。实际：`configuration-inspector.ts:240-245` 在 leader 退出时立即返回；真实 native 探针的同组 child 忽略 SIGTERM 后仍活，检查已 success 且 active=0。修正为已拥有进程组的完整退出确认与必要强杀，恢复路径同样覆盖 leader 先死；加最低进程 owner seam 的回归保护。探针已清理，未动 caller 栈。

### WARNING

- **V1-W1 — M1 必需验证尚未收口（证据缺口，不是推定产品缺陷）。** 契约：`design.md:117` M1 与 Agent Context 验证段；当前 `M1-catalog-lifecycle/evidence/implementation.md` 明确仍在实施。以下尚未获带固定版本/命令/结果/locator 的完整证据：最终本地/远端 CI；100 次真实刷新目录净增长为零、活动 worker 回零；至少 30 分钟/1000 HTTP 请求的 cold/cache 样本、p95/RSS/FD/目录；历史目录迁移副本筛选/幂等/中断恢复；representative ordinary/Global/PA 目录经配置投影对实际 session.capabilities、prompt preview 对真实 native assembly 的工具/Skills/workspace贡献保真；design 指定旧 reverse prepare waiter 持有旧 worker→插件变化推进两层 generation→新 settings 不加入旧 worker且旧值不写 snapshot 的真实跨层交错。caller 已在补其中多项；待一次性提交证据后逐项核对，复用有效结果，不需重复全量测试。

### SUGGESTION

无。

## Agent Context Evidence Boundary

复用本 reviewer 已完成的 `agent-context-review` Implementation Review，未再做一轮独立 checklist。确定性组装 seam 及已有 native tests 见 code-review.md。未发现 confirmed Context 内容缺陷；现有测试未完整满足 design 的跨模式 preview/assembly 对照，因此单列 V1-W1。未要求新增真实模型自由任务，亦未把 stub/native assembly 误称真实 provider 输入或模型行为证据。

## Evidence Reused

- `/tmp/refactor-682-im-tests.log`：5 files / 78 tests passed。
- `/tmp/refactor-682-inspector-tests.log`：1 file / 5 tests passed。
- `/tmp/refactor-682-native-presets.log`：2 files / 6 tests passed。
- `/tmp/refactor-682-model-regression.log`：2 files / 5 tests passed。
- 审查者读取上述日志的结尾并核对对应测试代码；具体版本追溯以 caller 实施记录为准，不能外推尚未完成的最终 CI。
- 审查者额外只执行 code-review F2 的一次真实 native 进程组探针；结果、方法和清理记录均在 code-review.md。未重跑 caller 正在执行的测试，没有自建长期运行栈。

## Round 2 — targeted-closure（最终）

- verification_mode: `targeted-closure`
- validated_at / effective_through: `8e0f327c81a3e0e6543f8ef3f22cd2ab7768c00c`
- executed_base / effective_base: `01c8e0b80`（本轮 main）
- backend_source: `bf0cdfdc32df872c9c40a0461c8284652d142d2f`
- finding_origin_head / fix_delta_range: `0812c67efe12174c429c372103fb8842891eed64` / `0812c67ef..bf0cdfdc3`
- focus_issues: V1-C1、V1-C2、V1-W1；包含新增保真/notification 修复和 main sync retained 判断。
- prior_verification_path: 本报告 Round 1。
- requires_full_verification: false；本轮未发现需要扩大 full review 的后端边界变化。
- verdict: **PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**。实现一致性、适用本地验证及产品证据已收口；不是远端 CI 或整个交付流程已完成的声明。

### Validated Issues

| Issue | 状态 | 契约与直接证据 |
|---|---|---|
| V1-C1 / F1 | closed | `main.ts:51` 捕获 cleanup_error 后继续启动；`/tmp/refactor-682-startup.json` 与检查脚本显示真实 Node online、独立 cron current、inspection readonly、未知身份资源保留。符合临时检查失败不阻断 durable Node 的设计。 |
| V1-C2 / F2 | closed | `configuration-inspector.ts:243-271` 确认完整组退出；recover 保留无已验证 leader 的存活组。新增真实 native 子进程忽略 SIGTERM 回归保护原触发原因。 |
| V1-W1：历史迁移副本 | evidence supplied | `/tmp/refactor-682-migration-check.mjs`、`migration.json`：真实锁定 DSH v4 header，2 candidates/5 protected，rename 后 ledger 前中断、重复恢复、rollback hash 不变；副本已清理，未执行生产迁移。 |
| V1-W1：native Context 保真 | closed | ordinary selected tools/Skills、Global/PA tools/Skills/PA section、workspace prompt/tool assembly 对照新增于原 fixture，属于最终 suite 通过范围；fidelity-r3 实际 1 file / 1 主旅程通过，较早 fix-tests 未算整轮通过。 |
| V1-W1：两层 generation 交错 | evidence supplied | `/tmp/refactor-682-race.mjs` / `race.json` 的真实 reverse prepare、shared inspector、native mutation、real CatalogReads，旧结果拒绝/新 worker与新目录/snapshot fence/active=0；明确不含 HTTP/relay，不扩大证据结论。 |
| V1-W1：100 次、30 分钟/1000 HTTP | closed | refresh100.json 100/100、每轮 home 空，active=0，p95/max 1320/1699ms；soak.json 1800.065秒/1001请求/0失败，6冷/995缓存，p95 2324.085/12.951ms，32资源采样均无 inspection/preview 净增长，FD固定39/20。 |
| V1-W1：最终本地测试/产品验收 | closed，保留全量重跑限制 | 最终 build/typecheck、frontend109files/1037tests、Python113、ruff、source-equivalent iOS-runtime、docs340/68、critical audit通过。后端全量838/840后对两个失败文件原树串行复验8/8通过；产品独立最终PASS。详见下节，不宣称单次全量绿。 |

### Retained / Final Sync

保留 Round 1 对 IM/RPC/Channels/所有 catalog/preview/prepare 入口及依赖边界的有效检查。fixed delta 未改这些产品代码；main 同步仅 bugfix-681 当前计划前端与文档，无后端交叉。Context Implementation Review 复用 code-review.md Round 2，不再额外进行一轮全 checklist。design 的 lease 澄清与既有 detached worker `pgid=pid` 一致，不是新机制。

最终 `bf0cdfdc3..8e0f327c8` 只有 evidence/产品报告与 lease 字段精确化，无 apps/packages 源码变化；因此本轮 fixed code 检查 retained 到 effective_through，corrected-delta 无新变化。当前 main 仍 `01c8e0b80`，没有额外待审 main delta。报告 Round 1 是历史失败快照，最终判断以本 Round 2 为准。

### 最终证据与限制

- **实际重建 / 长时读取：** 读取 `evidence/performance.md`、`/tmp/refactor-682-refresh100.json`、`/tmp/refactor-682-soak.json` 及 soak 脚本。100 次重建均成功且每轮 root 空；30 分钟 HTTP 链路全部 ready。脚本每600秒经正式协议刷新 token，按 captured_at 与请求起点分类；6 cold、995 cache，未把已有首个缓存当 cold。Node/IM RSS 首末69,184→58,336 /92,000→69,600KiB；FD始终39/20；32次采样 inspection/持久preview均0。有限样本不证明无限时长、真实聊天或其他负载无泄漏，100次 owner RSS增长也已在 performance.md 如实记录。受保护副本 `/Users/czj/.codex/reports/refactor-682-20261031/`，不在报告输出凭据。
- **独立产品验收：** `acceptance.md` Round2 / 已提交 `evidence/product-acceptance.json`，代码版本bf0cdfdc3。真实 HTTP 故障窗口验证last_known/readonly、插件/cron/usage/channel与其他Agent不受阻、恢复后ready；offline/save拒绝、重连恢复、正式logout后原token401；配置保存回读/旧版本409/32并发。原首轮冷读timeout保留，独占最终冷读1.28–1.87秒；未确定首轮负载根因。实际模型任务不在本unit验证范围，native assembly证据不冒称模型行为。
- **后端测试原始限制：** `/tmp/refactor-682-full-tests-r3.log`：`pnpm exec vitest run --maxWorkers=2`，151 passed/2 failed files，838 passed/2 failed tests，374.86秒。失败为未修改的 `agent-disable-native` PTY cleanup与 `task-execution-limits` 45秒等待；未修改对应源码/测试，随后两个文件 `--maxWorkers=1` 2files/8tests通过（`full-failure-recheck.log`，71.13秒）。新增catalog/inspector/preview保真断言属于全量通过范围。此次验证有全部测试覆盖及失败项同树复验，**没有单次全量绿，也没有已确认失败根因**；远端必需CI继续承担独立环境门禁。
- **其他本地验证：** 最终 `/tmp/refactor-682-final-build.log` / `final-typecheck.log` 通过，installer只为本地candidate；`frontend-r2.log` 109files/1037tests通过；Python113passed/28e2edeselected，ruff check/format通过；iOS-runtime为source-equivalent结果，本unit未改iOS；`docs-prearchive.log`340 maintained sources/68routes通过；critical audit无critical（已有其他等级告警未宣称全零）。未重复执行负载。
- **后续交付门禁：** `change-workflow.md:199-205` 明确final sync/静态门禁有效性与delta核对→canonical归并→本地检查→archive→Ready PR与远端CI。当前本地验证PASS允许owner继续这些步骤；远端CI尚未执行，仍须在PR后全部通过才能交付，不能把本报告写成远端CI已通过。归并/归档后的文档路径检查及隔离栈清理由caller完成。

## Corrected Delta Reconciliation

- verification_mode: `corrected-delta`
- validated_at / effective_through: `8e0f327c81a3e0e6543f8ef3f22cd2ab7768c00c`
- executed_base / effective_base: `01c8e0b80`；backend_source: `bf0cdfdc32df872c9c40a0461c8284652d142d2f`。
- scope: 本 unit 全部 IM/Gateway delta 及最终 unit diff 的遗漏对外行为；main 自带 bugfix-681 排除于本 unit。

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| IM 同 owner/绑定/连接/workspace/profile 最多五分钟内存候选，保存新校验 | `catalog-reads.ts` scope/TTL/current fence；Node 真 config；native prepare 不走 IM cache | Round 1 IM 窄 suite；native fixtures；race 组合证据 | aligned |
| IM 连续/并发读不占写锁，失败 last-known/readonly，权限/配置/绑定/连接迟到拒绝 | settings route 移出 serialized，等待后鉴权/profile/connection/current fence；RPC transient deadline/cancel | Round 1 IM/RPC tests，startup真实降级；最终产品HTTP PASS | aligned |
| Gateway 临时检查不写持久聊天 home，成功/失败/取消释放，异常退出下次回收 | 独立官方 worker/home、generation/waiters/预算、组级 reclaim，startup error 不阻断 Node | inspector native tests、child regression、startup mismatch、race active=0、100实际重建/30分钟HTTP | aligned |
| Gateway 有界失败、不重启聊天、保存真实候选和权限 | 7/8/9 秒边界与独立 worker；prepare/preview 原语保持 native 组装/校验 | 死循环timeout/恢复保留聊天PID；native tools/Skills/prompt对照与最终产品故障旅程 | aligned |

### Uncovered Observable Behavior

无遗漏的本 unit 对外行为。内部 `node.request.cancel`、`node.capabilities.changed` 和错误码是实现有界生命周期/候选失效的节点间机制；用户可观察结果已由上述“连续读取与故障后恢复”和“临时检查不污染或阻塞持久执行”覆盖。没有新增 UI 或客户端操作规则。普通 mount/重复 watch 不再发布失效，真实 native mutation 发布；外部文件仍按 TTL 反映，符合现有目标。

Outcome: **aligned**。最终证据提交未修改 delta 或后端实现，无新delta变化。实现与适用本地退出证据已对齐；此结论不代替current spec归并、archive或PR后的远端CI。
