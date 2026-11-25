# perf-789: Review

## 范围与版本

- 本次问题与需求/设计位置：[`motivation.md`](motivation.md)、[`design.md`](design.md)、[`specs/gateway/personal-agent.md`](specs/gateway/personal-agent.md)
- 实际 `executed_base` / `validated_at`：`4ff83afda84a2ba67047524cb559e8b2f8655fb1` (`origin/develop`) → Round 1 `720d501f200e767f32685d35f68f677f732a0843` → Round 2 `8fe749145fef975d0e6e10c09940941310849af8`
- 最终 `effective_base` / `effective_through` 与保留依据：`4ff83afda84a2ba67047524cb559e8b2f8655fb1` → `8fe749145fef975d0e6e10c09940941310849af8`（`origin/develop` 未前移；后续交付提交仅包含本 `review.md`、已核准契约归并与单元归档移动，未修改任何受审实现或测试代码，独立审查结论完整保留）。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 合批时间线、共同群双路投递合并与回执结清、`review_due_at` 后台调度与重启恢复、全读取/外发冲刷边界、`context_overflow` 二分拆批、范围清退与最终契约一致性 | `change-code-review`，独立审查子代理（`5ee57c31`），`full`（`4ff83afda..720d501f2`）+ `patch` / `closure` / `corrected-delta`（`720d501f2..8fe749145`） | `pass` | 逐行审查全部受影响模块及上下游调用链，并在内存 SQLite 复现核验 Round 1 三项边界问题全部关闭；96 项 IM/PA 测试、11 项 DSH 安全测试、运行时依赖契约及 `corrected-delta` 均对齐通过。 |
| 批量输入审核模型实际收到的单模态提示词、紧凑 `timeline`（`item: 1..k` 与 `needs_decision: false` 背景证据、`omissions`）及主 PA 主动读取/外发前的未审原文隔离 | `agent-context-review`，独立审查子代理（`5ee57c31`），实施模式（含 Round 2 复验） | `pass` | 独立审查者亲自通读真实组装入口捕获的批量请求原件（`system` `1,105` tokens + `user` `2,016` tokens）及组装/消费代码：单条与批量提示词严格分模态、无 `needs_owner` 丢消息黑洞、不连坐后续正常发言者，且主 PA 侧 `inbox`、`read_messages`、`search_messages` 与外发 `send`/`external`（含在途 `reviewing` 批次与飞书 `f_xxxxxx` 影子会话）均已阻断未审原文提前暴露。限制：受控样本的模型响应部分由测试与合成载荷验证，未额外采集公网远端模型实跑轨迹。 |
| 参与群连续普通消息与混合消息场景下，审核请求数与输入/输出 token、管线耗时达标且保持唤醒、已读消重、控制取消与安全准入不变量 | `performance-review`，独立审查子代理（`5ee57c31`），实施模式（含 Round 2 复验） | `pass` | 独立只读复跑基准脚本并用 `@deepseek-ai/dsh-token-meter/estimate` 核对（见 [`benchmark-and-context.md`](M1-batch-input-review/evidence/benchmark-and-context.md)）：样本 A 请求数 `20 → 1`（`-95.0%`）、累计输入 tokens `74,875 → 3,286`（`-95.6%`，目标 `≤ 8,000`）；样本 B 请求数 `22 → 2`（`-90.9%`）、累计输入 tokens `81,994 → 5,685`（`-93.1%`，目标 `≤ 15,000`），本地管线 `16.75–20.27 ms`，唤醒次数、已读消重、控制命令取消及安全准入不变量全部保持。限制：不含公网远端 LLM 推理墙钟延迟与缓存计费。 |

## Findings 与关闭

- **R1-F1**（`packages/personal-assistant/src/global-agent.ts:369-375`，关联 `attention.ts:32-34`、`apps/im-server/src/personal-agent.ts:266,328`）：共同 Web IM 群中主人发送 `@PA /stop` 等控制命令时，先到的无 `participants` 观察事件将其置为普通 `admitted` 并触发唤醒，后到的 `relay.message` 命中 `state === 'admitted'` 早退守卫导致控制命令被吞没。
  - 严重度 / 证据状态：`CRITICAL` / `CONFIRMED`。
  - Resolution（`8fe749145`）：IM `admitSource` 与 `observations` 补充权威 `agent_user_id` 并由节点透传至 `controlText`（兼容唯一寻址观察事件）；新增 `InboxStore.markControlHandled` 原子记录已认证控制元数据与 `personal_control_handled = true`、`consumed = 1` 并清理 `inbox_schedule`，仅在 `personal_control_handled === true` 时去重跳过，补充双路回归测试。
  - 独立关闭依据与版本：独立审查者（`5ee57c31`）在 `8fe749145` 核查代码并实跑含/不含 `agent_user_id` 两种双路复现实验，均确认 `stopCalls: 1, wakeSubmits: 0`，判定 **`closed`**。
- **R1-F2**（`packages/personal-assistant/src/personal-assistant.ts:175-181`，关联 `inbox-review.ts:75-80`）：`flushReviews` 在 `conversationId === undefined` 时仅查 `review_state = 'pending'`，漏等 `this.reviewBatches` 中已进入 `reviewing` 的在途批次，导致跨会话 `search_messages` / `read_messages` / `inbox(check)` 绕过正在执行的审核。
  - 严重度 / 证据状态：`CRITICAL` / `CONFIRMED`。
  - Resolution（`8fe749145`）：`InboxReviews.pendingConversations` 扩展覆盖 `review_state IN ('pending', 'reviewing')`，`PersonalAssistant.flushReviews` 同时并入该 `agentId` 的内存活跃 `reviewBatches` 键并复用单会话单飞 Promise 等待结算，补充并发挂起回归测试。
  - 独立关闭依据与版本：独立审查者（`5ee57c31`）在 `8fe749145` 实跑并发挂起实验确认跨会话查询严格等待在途批次结算为 `rejected` 后才执行，判定 **`closed`**。
- **R1-F3**（`packages/personal-assistant/src/global-agent.ts:869-870,910-922` 与 `personal-assistant.ts:475-483,570-574`）：飞书 PA 参与群的 `f_xxxxxx`（`external:...`）引用在主动查询/读取及外部渠道发送前未通过 `store.imConversation` 映射回 IM `shadowId`，导致前置冲刷与 `held_for_revalidation` 重验落空。
  - 严重度 / 证据状态：`HIGH` / `CONFIRMED`。
  - Resolution（`8fe749145`）：新增 `GlobalAgent.resolveReviewConversation` 将 `external:...` 还原为 `shadowId`（未映射或用户/Agent 引用回退为全会话冲刷），并在 `PersonalAssistant.send` 的 `external:` 分支及 `external` 发送边界前对 `shadowId` 执行冲刷与 `inbox.blocking` 重验，补充 `f_xxxxxx` 查询与发送回归测试。
  - 独立关闭依据与版本：独立审查者（`5ee57c31`）在 `8fe749145` 实跑 `f_xxxxxx` 复现实验确认查询与外发前均已冲刷并拦截，判定 **`closed`**。

最终状态：**无存活 findings**。

## 流程收口

- 重要目标和关键设计覆盖：[`motivation.md`](motivation.md) 全部用户侧不变性场景、量化性能目标与 [`design.md`](design.md) 全部 5 项关键决策、M1 退出标准均已实现并通过独立验证。
- 开放问题 / pending / inconclusive：无。
- 最终 delta 校对：独立代码审查（`5ee57c31`）在 `8fe749145` 校对 [`specs/gateway/personal-agent.md`](specs/gateway/personal-agent.md) 与 canonical `docs/specs/gateway/personal-agent.md` 及最终实现/测试，判定 **`aligned`**（Requirement 总数保持 19 不变）。
- 版本变化后保留 / 补验的判断与依据：Round 1 (`720d501f2`) → Round 2 (`8fe749145`) 针对全部受影响链路完成了独立 `patch`、`closure`、`agent-context-review`、`performance-review` 与 `corrected-delta` 复验；`8fe749145` 之后的交付提交仅含归并文档与归档移动，无代码变更，全部独立判断保持有效（`retained`）。
- 测试资源回收结果：本单元全程使用内存 SQLite 与 Vitest 子进程，未启动 worktree 常驻服务；仓外暂存基准脚本位于当前会话 scratch 目录，worktree 工作区干净无残留临时产物。
- 交付范围与剩余事项：完成 canonical spec 归并、change unit 归档、本地 CI 等价门禁检查，向 `develop` 提交 PR（关联 `Closes #533`）并保留开发 worktree 待合入后清理。
