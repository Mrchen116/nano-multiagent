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
