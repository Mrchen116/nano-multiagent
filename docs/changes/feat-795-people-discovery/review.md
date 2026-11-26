# feat-795: Review

## 范围与版本

- 本次问题与需求/设计位置：[`spec.md`](spec.md)、[`design.md`](design.md)、[`design-review.md`](design-review.md)、[`specs/im/agents-nodes.md`](specs/im/agents-nodes.md)、[`specs/im/web-chat-ux.md`](specs/im/web-chat-ux.md)、[`M1-people-discovery/evidence/walkthrough.md`](M1-people-discovery/evidence/walkthrough.md)
- 实际 `executed_base` / `validated_at`：`3fafe61c5` (`origin/develop`) → Round 1 `c79b3530d6b4614d3b9a0ecbff0cc8ed135f3533` → Round 2 `0ba941e87c83b82c04ecefd9bd27ebb70f0b8c41`
- 最终 `effective_base` / `effective_through`：`3fafe61c5` → `0ba941e87c83b82c04ecefd9bd27ebb70f0b8c41`（本提交仅归集 `review.md` 记录，产品实现、测试与 delta-specs 与 `0ba941e87` 完全一致）。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 跨包架构边界、`/im/v1/contacts` 真人 `username` 与 Agent `owner_user_id`/`owner_display_name` 对齐、`/people` SPA 路由白名单、外部渠道未映射代记发送者隔离、公开 PA 与专业数字员工隐私边界、保留草稿的 `@` 提及追加及最终 2 份 delta-specs 校对 | `change-code-review`（含 `corrected-delta`），[Stage 4 Code Reviewer](conversation://af1d4c14-0568-419e-b55a-473a3f70fc10)，Round 1 `full`（`9cfa04340..c79b3530d`）+ Round 2 `patch` / `closure` / `corrected-delta`（`c79b3530d..0ba941e87`） | `pass` | 逐文件审查 31 个代码/测试变更文件；核实 `apps/im-server` 全量测试（`76` 文件 `512` 用例）、前端全量测试（`134` 文件 `1,301` 用例）与 Round 2 增量回归测试（`3` 文件 `30` 用例）、`pnpm build`、`python3 scripts/e2e_ui.py`、`test_runtime_dependency_contract.py`（`14 passed`）及 `./scripts/docs-check` 全部通过。Round 1 四项问题（`F1`–`F4`）在 `0ba941e87` 全部独立复核关闭；2 份 delta-specs 最终校对均为 **`aligned`**。 |
| 桌面（`1280×820`）与移动（`390×844`）找人全链路信息组织、自明性、次级按钮视觉权重、上下文 `PersonPopover`、选人/建群/群详情人本分组、Agent 公开资料页联系管理员、移动端 5 项底栏未读角标锚定与中英文对称覆盖 | `frontend-experience-review`，[Stage 4 Code Reviewer](conversation://af1d4c14-0568-419e-b55a-473a3f70fc10)，实施模式（Round 1 代码与样式核查 + Round 2 隔离真栈 8 张桌面/移动实测截图目视复核） | `pass` | 目视核验隔离真栈 `http://127.0.0.1:56708` 实拍的 8 张高分屏画面（桌面 `/people`、聊天侧栏「同事」Tab、侧栏 `⌘K` 搜索召回 `@linxia`、群聊头像 `PersonPopover`、新聊天分类筛选弹窗、群聊信息混合头像簇与加人列表、公开数字员工资料页联系管理员、移动端 `/people` 与 5 项底栏及角标）：界面自明、操作主次协调、窄屏自适应无溢出截断、浏览器 `0` `pageerror`。 |

## Findings 与关闭

- **F1**（`src/IM/frontend/src/features/people/people-directory-page.tsx`）：未加入团队的个人空间态在渲染 `people-personal-space-guide` 引导条的同时仍继续渲染下方 `.im-directory-content`，且本人行的 PA 胶囊复用了「公开个人助手」文案。
  - 严重度 / 证据状态：`WARNING` / `CONFIRMED`。
  - Resolution（`0ba941e87`）：改为 `!isActiveMember` 时仅渲染个人空间引导横幅（严格互斥）；活跃成员列表中 `isSelf` 行的 PA 标签改为 `pa.label`（「个人助手 / Personal assistant」），并补充 `people-directory-page.test.tsx` 回归断言。
  - 独立关闭依据与版本：`af1d4c14` 在 `0ba941e87` 复核代码、单测与截图 `01` / `08`，判定 **`closed`**。
- **F2**（`src/IM/frontend/src/features/chat/components/message-pane.tsx`）：从群聊右侧/移动端全屏 `ThreadColumn` 内的正文 `@mention` 胶囊打开 `PersonPopover` 点击「`@` 提及」时，提及内容写入了主时间线输入框而非当前话题输入框。
  - 严重度 / 证据状态：`WARNING` / `CONFIRMED`。
  - Resolution（`0ba941e87`）：通过 `personAnchor.element.closest(".chat-thread-column")` 识别话题列触发源，在 `openThreadId` 非空时将 `@显示名 ` 与 `draftMentions` 写入 `threadDraftKey(conversation.id, openThreadId)` 并在下一帧聚焦 `.chat-thread-column textarea`，补充 `person-popover.test.tsx` 回归单测。
  - 独立关闭依据与版本：`af1d4c14` 在 `0ba941e87` 复核代码与单测，判定 **`closed`**。
- **F3**（`src/IM/frontend/src/features/chat/components/conversation-sidebar.tsx`）：侧栏 `matchedContacts` 与 `unchattedColleagues` 去重循环未排除 `direct_kind === "agent-agent"` 或 `is_observer` 的双 Agent 协作观察会话，可能误抑未私聊公开 Agent 的「联系人」搜索召回。
  - 严重度 / 证据状态：`WARNING` / `CONFIRMED`。
  - Resolution（`0ba941e87`）：两处去重均显式跳过 `c.direct_kind === "agent-agent" || c.is_observer`，并在 `conversation-sidebar.test.tsx` 增加观察流与联系人搜索并存测试。
  - 独立关闭依据与版本：`af1d4c14` 在 `0ba941e87` 复核代码与单测，判定 **`closed`**。
- **F4**（`src/IM/frontend/src/features/chat/chat-workspace-page.tsx`）：从 `GroupSettings` 成员列表打开 `PersonPopover` 后按 `Escape` 或外部点击关闭时，未将键盘焦点归还至触发成员按钮。
  - 严重度 / 证据状态：`MINOR` / `CONFIRMED`。
  - Resolution（`0ba941e87`）：在 `GroupSettings` 挂载的 `PersonPopover` `onClose` 中对仍挂载的触发元素执行 `focus({ preventScroll: true })`，对齐 `MessagePane` 焦点恢复语义。
  - 独立关闭依据与版本：`af1d4c14` 在 `0ba941e87` 复核代码，判定 **`closed`**。

最终状态：**无存活 findings（0 open）**。

## 流程收口

- 重要目标和关键设计覆盖：[`spec.md`](spec.md) 与 [`design.md`](design.md) 的全部 4 组 Requirement/Scenario（一级 `/people` 同事目录与人机关系呈现、聊天侧栏 `⌘K` 穿透搜索与「同事」Tab 直达、群聊头像/双路径正文 `@mention`/群成员列表 `PersonPopover` 与 Agent 资料页联系管理员、新聊天/建群/群详情人本分组与 `@username` 展示及中英文双语对齐）均已实现并通过独立审查。
- 开放问题 / pending / inconclusive：0 项代码或设计遗留问题；尚待用户在保留的隔离测试服务上完成亲自试用体验。
- 最终 delta 校对：独立代码审查（`af1d4c14-0568-419e-b55a-473a3f70fc10`）在 `0ba941e87` 完成 `corrected-delta` 核对，[`specs/im/agents-nodes.md`](specs/im/agents-nodes.md) 与 [`specs/im/web-chat-ux.md`](specs/im/web-chat-ux.md) 均判定为 **`aligned`**（其他包无 spec delta）。
- 测试资源保留台账（用户明确要求保留）：
  - **隔离运行栈**：`WT_ROOT=/tmp/nano-e2e-feat-795`，入口 `http://127.0.0.1:56708`，`IM_PID=66944`（`/tmp/nano-e2e-feat-795/.im.pid`），`GW_PID=66974`（`/tmp/nano-e2e-feat-795/.gateway.pid`），与生产 `~/.nanoassistant` 及 `8011`/`5173` 完全隔离；
  - **Owner 与回收触发**：由接手本任务收尾或执行归并/PR 的 Agent 在用户反馈体验完成后，执行 `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-795-people-discovery/scripts/e2e-down.sh --wt /tmp/nano-e2e-feat-795` 停止并清理临时目录。
- 交付范围与剩余事项：遵循 `change-orchestrator-simple`“尚待用户试验的 unit 保持 active，不能宣称试验通过”的规则，当前分支 `unit/feat-795-people-discovery` 保持 `docs/changes/feat-795-people-discovery/` 为 active 状态，待用户亲自测完确认后，即可执行 delta-specs 归并、`archive/` 归档与 PR 提交。
