# feat-796-agent-privacy-scope: Review

## 范围与版本

- **本次问题与需求/设计位置**：[spec.md](spec.md)、[design.md](design.md)、[design-review.md](design-review.md)、[M1-agent-privacy-scope/walkthrough.md](M1-agent-privacy-scope/walkthrough.md)、[M1-agent-privacy-scope/evidence/browser-journey.md](M1-agent-privacy-scope/evidence/browser-journey.md)，以及 12 份 delta-spec（`specs/im/{spec,agents-nodes,personal-agent,conversations-messages,agent-work,auth-tenancy,web-chat-ux,ios-client}.md` 与 `specs/gateway/{global-agent,personal-agent,routing-delivery,external-channels}.md`）。
- **实际 `executed_base` / `validated_at`**：
  - `executed_base`：`95f074c7a74516efe33bf1bd0c41553b1919e208`
  - Round 1 `validated_at`：`f08a5d6d2c71d1f1680869100ff70f82b69329`（`f08a5d6d2c71d1f1680869100ff70f82b6929329`）
  - Round 2 `validated_at`（同步 `origin/develop` 并关闭 Round 1 建议后）：`1fd7805360acb57ad172775d19a3ed19cd52fcda`
  - Round 3 `validated_at`（修复合并后 `TaskGraphService` 与 `task_context` 撤销增量后）：`332b707db97328734b5e64b3a80df885646882be`
- **最终 `effective_base` / `effective_through` 与保留依据**：
  - `effective_base`：`22eb4879c`（同步 `feat-797` 后的最新 `origin/develop`，基于 Round 3 审查锚点 `bf20e1da2d87fd3f8c35689beb20c719b1fa4147` 仅解决 3 处无语义交集的 canonical spec 文档合并冲突）
  - `effective_through`：`332b707db97328734b5e64b3a80df885646882be`
  - 保留依据：所有生产代码、测试修复与合并后增量审计均在 `332b707db97328734b5e64b3a80df885646882be` 收口并通过独立审查，`feat-797` 代码零冲突自动合入并通过回归测试，其后仅保留 12 份 `aligned` delta-spec 归并、`review.md` 与 change unit 归档。

---

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 两档权限（`team` 默认 / `owner_only` 私有）在普通/全局 Agent 与 PA 全入口一致生效、个人空间有效成员 `team` Agent 跨空间协作/Work/轨迹开放、同主人跨空间内部专属群与 `agent-agent` 私聊互通、外部群互斥与收紧自动退群、历史同事 1:1 私聊冻结只读与可逆恢复、私有 PA 静默旁观与对外发送/代发/飞书拦截、`TaskGraphService` 跨空间与私有安全及 `task_context` 撤销联动 | `change-code-review` · 独立子代理 `b52fe6d6-32c7-48fa-ae8c-5b3d0b3ba4e4`（Round 1 `full` + Round 2 合并后 `patch & closure` + Round 3 `closure & patch`） | `pass` | Round 1 `0 CRITICAL / 0 WARNING`（3 项非阻塞建议已关闭）；同步 `origin/develop`（`feat-785` 等）后 Round 2 检出 `1 CRITICAL / 2 WARNING`（`TaskGraphService` 私有崩溃与跨空间任务盲区、冻结私聊任务写入漏口、收紧时 `task_context` 捕获顺序），在 `332b707db` 全部修复并由 Round 3 独立复核确认 `0 CRITICAL / 0 WARNING`。全仓构建、类型检查、后端与合约 Vitest（155 文件 / 1,041+ 用例）、Web Vitest（134 文件 / 1,308+ 用例）、iOS Simulator 编译与 `pytest -m "not e2e"`（138 用例）全绿。 |
| 12 份 delta-spec 与同步后 `docs/specs/{im,gateway}/`、`design.md` 及最终实现的一致性 | `change-code-review` · 独立子代理 `b52fe6d6-32c7-48fa-ae8c-5b3d0b3ba4e4` · `corrected-delta` | `pass` (`aligned`) | 逐文件核对全部 12 份 delta-spec（含融入 `feat-785` 主动筹划与焦点台条款后的 `im/spec.md`、`im/ios-client.md`、`im/personal-agent.md` 及修复 L16 提示表述后的 `im/web-chat-ux.md`），Requirement 计数（`im/conversations-messages` 在 `feat-797` `40` 基线上 `+1 -> 41`，其余不变）与行为条款 `12 / 12 aligned`。 |
| Web（桌面 `1280×820` / 手机 `390×844`）与原生 iOS 全创建/编辑入口两档选择、Onboarding Step 2 窄屏首屏主按钮可达、建群/群详情互斥置灰与原因说明、冻结私聊只读横幅与个人置顶/免打扰保留 | `frontend-experience-review` · 独立子代理 `b52fe6d6-32c7-48fa-ae8c-5b3d0b3ba4e4`（真实隔离栈双视口截图与源码审查 + Round 2 `closure`） | `pass` | 逐张核验隔离真实栈 Chromium 9 项双视口旅程截图（Onboarding Step 2 `390×844` 主按钮 `bottom = 782px <= 844px`、PA 弹窗直接建私有、普通 Agent 创建/编辑两档卡片、建群互斥锁定私密、同事视角隐藏私有助手、历史 1:1 私聊 `agent_private` 横幅隐藏输入框并保留置顶/免打扰、恢复 `team` 即时解锁）；Round 1 关于移动端加人子视图提示与 iOS 列表行侧滑置顶/免打扰的 2 项建议已在 `ab92a4434` 关闭。限制：原生 iOS 通过 `xcodebuild` Simulator 构建、`Runtime` 单测与 SwiftUI 源码核验，未额外执行 Simulator 手工触控录屏。 |
| PA 代建 `agent_creation(options)` 与 `nano-agent-creation` Skill 指引、私有 PA / 普通 Agent 外发 `not_sent (collaboration_scope_restricted)` 模型可见报错、收紧后 `InboxStore` / `SingleThread` / `task_context` 撤销投影与单纯切换 `collaboration_scope` 零缓存前缀重写 | `agent-context-review` · 独立子代理 `b52fe6d6-32c7-48fa-ae8c-5b3d0b3ba4e4`（只读 `tsx` 实时调用检查 + Round 2/3 `closure & patch`） | `pass` | 实测核验 `agent_creation(action="options")` 架构描述与默认值、`nano-agent-creation/SKILL.md` 对齐清单、`send_message` / `send_user_message` 在 IM 与飞书非主人会话的清晰可行动 `not_sent` 文案、`InboxStore.restrict` 与 `access_revoked` 最小脱敏撤销通知，以及 `candidateFingerprint` / `applyRevisionOnly` 在仅切换 `collaboration_scope` 时保持缓存前缀零重写、零配置分界线。 |

---

## Findings 与关闭

- **`R1-REC-1` (`Recommendation`) — `packages/personal-assistant/assets/skills/nano-agent-creation/SKILL.md:15` 对齐清单沿用旧「群聊回复方式」措辞**
  - 修复：在 `ab92a4434` 更新为「及协作范围（团队公开 / 私有）」，与 `agent_creation(action="options")` 返回字段一致。
  - 状态：`closed`（Round 2 `b52fe6d6-32c7-48fa-ae8c-5b3d0b3ba4e4` 独立确认）。

- **`R1-REC-2` (`Recommendation` + `delta-mismatch`) — `group-settings.tsx` 移动端 `adding` 子视图缺少私有助手禁选真人原因说明，且 `specs/im/web-chat-ux.md:16` 群详情置灰措辞与实现不一致**
  - 修复：在 `ab92a4434` 为移动端 `isMobile && adding` 子视图补充 `privateAgentVisibilityLocked` 提示，并将 `specs/im/web-chat-ux.md:16` 校正为「锁定为私密（禁用公开可见性切换并显示原因说明）且在『添加成员』中不提供外部真人同事」。
  - 状态：`closed`（Round 2 `b52fe6d6-32c7-48fa-ae8c-5b3d0b3ba4e4` 独立确认）。

- **`R1-REC-3` (`Recommendation`) — 原生 iOS `ChatListView.swift:283` 会话列表侧滑/长按菜单在 `agent_private` 历史私聊上隐藏了个人置顶/免打扰**
  - 修复：在 `ab92a4434` 将过滤条件收窄为 `chat.can_write == false && chat.write_blocked_reason != "agent_private"`，保留个人置顶与免打扰操作。
  - 状态：`closed`（Round 2 `b52fe6d6-32c7-48fa-ae8c-5b3d0b3ba4e4` 独立确认）。

- **`R2-C1` (`CRITICAL`) — 同步 `origin/develop`（`feat-785`）后 `TaskGraphService` 对 `company:default` 内 `owner_only` Agent 执行 `list`/`focus`/`executionScopes` 崩溃，且个人空间 `team` 全局 Agent 无法读取 `company:default` 跨空间任务**
  - 根因：`TaskGraphService.accessibleSpaces` 对非 PA Agent 硬编码单空间 `[profile.space_id]`，且 `list`/`focus` 仅对 `personalRead` 前置过滤 `this.chat(...)`，导致 `owner_only` Agent 命中公开群或冻结私聊任务行时在 `projection` 抛出 `not_found_or_forbidden`。
  - 修复：在 `332b707db` 更新 `apps/im-server/src/task-graphs.ts` 的 `accessibleSpaces`（按 `agentAvailable` 与 owner 空间资格覆盖 `company:default` 及 `personal:<owner_id>`），并在 `list` 与 `focus` 统一前置 `!!this.chat(conversation_id, user)` 过滤；补充 `agent-privacy-visibility.test.ts` 回归测试。
  - 状态：`closed`（Round 3 `b52fe6d6-32c7-48fa-ae8c-5b3d0b3ba4e4` 独立确认）。

- **`R2-W1` (`WARNING`) — `TaskGraphService.writable` 未校验 `!c.can_write`，外部同事仍可在冻结 `agent_private` 1:1 私聊中写任务图**
  - 修复：在 `332b707db` 于 `writable` 拦截 `!c.can_write`，并将 `write_blocked_reason === "agent_private"` 映射为 HTTP `403 { detail: { code: "agent_private" } }`，同时保留既有任务图只读查询。
  - 状态：`closed`（Round 3 `b52fe6d6-32c7-48fa-ae8c-5b3d0b3ba4e4` 独立确认）。

- **`R2-W2` (`WARNING`) — `control.ts` 在调用 `captureTaskContextAccess` 前已更新 `agent_profiles.collaboration_scope` 且未覆盖 `frozenDirects`，导致收紧为私有时漏写 `task_context_index(..., 'revoked')`**
  - 修复：在 `332b707db` 调整 `control.ts` 在 `UPDATE agent_profiles` 前捕获全会话 `beforeTaskAccess` 并传入 `applyCollaborationScopeTransitionInTx`，统一为退出的外部群、冻结同事私聊与失权外部影子会话写入 `projection_kind='revoked'`，并在 `gateway.ts` 与 `global-agent.ts` 放行最小脱敏 `access_revoked` 撤销通知投递。
  - 状态：`closed`（Round 3 `b52fe6d6-32c7-48fa-ae8c-5b3d0b3ba4e4` 独立确认）。

---

## 流程收口

- **重要目标和关键设计覆盖**：完整覆盖 [spec.md](spec.md) 与 [design.md](design.md) 全部验收条件，无未完成里程碑。
- **开放问题 / pending / inconclusive**：无开放 `CRITICAL` 或 `WARNING`；原生 iOS 已完成 Simulator 构建、Runtime 单测与源码/契约审查（未做 Simulator 手工 UI 录屏）。
- **最终 delta 校对**：12 份 delta-spec 全部 `aligned`，可直接归并至 `docs/specs/{im,gateway}/`。
- **版本变化后保留 / 补验的判断与依据**：同步 `origin/develop`（`bf20e1da2`）后执行了全量构建、类型检查、iOS 编译、合并冲突审查与 `TaskGraphService` 交互补验；`332b707db` 未触及前端界面代码，Web 真实隔离双视口证据保持有效。
- **测试资源回收结果**：隔离 E2E 服务栈（`./scripts/e2e-down.sh`）、临时 SQLite/workspace、浏览器实例与审查临时目录均已完整回收并核实无残留进程；截图保存在仓库外 artifact scratch 目录，未入库。
- **交付范围与剩余事项**：归并 12 份 canonical spec、归档 unit 目录至 `docs/changes/archive/feat-796-agent-privacy-scope`，推送分支并创建指向 `develop` 的 PR；按仓库规则在 PR 合入前保留 `.worktrees/unit-feat-796-agent-privacy-scope`。
