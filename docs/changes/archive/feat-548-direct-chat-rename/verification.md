# Verification Report: feat-548

> Validation snapshot: `f455c6220 → 298987e90172903436302725092f9856097d423c`

## Summary

Mode: full
Delta range: `74284146e28e31964189de6f19e6c2099bdf6f0f..298987e90172903436302725092f9856097d423c`
Focus issues: N/A
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 5/6 |
| Correctness | 6/7 |
| Coherence | Followed |

0 critical issue(s), 1 warning(s) found. Fix before PR.

## Completeness

- Tasks: 3/4 complete。`M1-impl/tasks.md` 的实现、标题统一与真实页面/Agent 名称读取均有代码、测试及 `M1-impl/progress.md` 证据；未勾选项是本轮独立 closure、后续 canonical 归并与最终 CI。它不表示另有缺失的产品实现，但当前两条受影响的前端集成测试尚未随菜单入口更新，因此 W1 的“相关测试通过”尚未满足。
- Spec 覆盖：3/3 requirements 均有实现。私聊菜单及改名状态位于 `src/IM/frontend/src/features/chat/components/direct-conversation-menu.tsx:11`；会话级 PATCH、列表/顶部刷新与工作视图名称刷新位于 `src/IM/frontend/src/features/chat/chat-workspace-page.tsx:921` 和 `src/IM/frontend/src/features/chat/components/message-pane.tsx:792`；持久自定义标题、外部正常同步/竞争恢复保护与旧库增列位于 `src/IM/infra/repositories/conversations.py:237`、`:333`、`:397` 和 `src/IM/infra/db.py:34`、`:501`；Agent 查询统一读取 `conversation.title` 位于 `src/IM/application/work_conversations.py:67`、`:104`。
- Milestone exits：R1–R5 均有实现与可复查证据；W1 因下述两条旧集成断言失败而未闭合。独立运行后端聚焦用例为 8 passed；菜单组件为 4 passed；旧 workspace 集成用例为 2 failed。
- Prototype / Reference 覆盖：design 的两条 must-match 均投影到 R1/R2。桌面/手机菜单、保存、失败和刷新后的状态记录在 `M1-impl/progress.md`，原始定位为原 unit worktree 的 `output/direct-chat-rename/{desktop-menu-final.png,mobile-menu.png,mobile-saved.png,failure-final.png,live.json,request-audit.json}`。检查可见菜单结构、移动端紧凑入口和最终通用错误文案与原型契约一致；早期 `mobile-failure.png` 含旧内部错误文案，但较晚的 `failure-final.png` 与最终代码 `direct-conversation-menu.tsx:55-57` 已替代该状态。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 私聊提供会话菜单 / 从菜单访问会话操作 | `src/IM/frontend/src/features/chat/components/message-pane.tsx:792`; `src/IM/frontend/src/features/chat/components/direct-conversation-menu.tsx:62` | `direct-conversation-menu.test.tsx:15` 通过；两条旧 workspace 集成断言失败 | warning |
| 私聊改名 / 修改已有私聊名称 | `chat-workspace-page.tsx:921`; `message-pane.tsx:792`; `direct-conversation-menu.tsx:47` | `direct-conversation-menu.test.tsx:31`; `test_users_conversations_api.py:213`; 真实桌面/手机与刷新证据 | covered |
| 外部私聊后续同步保留手动改名 | `src/IM/infra/repositories/conversations.py:237`; `:333`; `:397` | `tests/im_service/unit/test_conversation_custom_title.py:30`; `:54`; `live.json` | covered |
| 同一 Agent 的其他会话保持原名 | `src/IM/infra/repositories/conversations.py:397` 的 conversation-id scoped update | 真实双会话结果记录于 `M1-impl/progress.md` 和 `live.json` | covered |
| 取消或提交空名称 | `direct-conversation-menu.tsx:47`; `:107`；后端 `conversations.py:409` | `direct-conversation-menu.test.tsx:31`; `:69` | covered |
| 保存失败可重试 | `direct-conversation-menu.tsx:47-59`; `:91-110` | `direct-conversation-menu.test.tsx:48`; `failure-final.png` | covered |
| Agent 使用用户设定的会话名 / 修改后读取 | `src/IM/application/work_conversations.py:67-79`; `:104-124` | `tests/im_service/integration/test_agent_work_api.py:152-198`; `live.json`; `request-audit.json` | covered |

刷新后的列表/顶部一致性由成功后 invalidation `chat-workspace-page.tsx:923-926` 与两处对同一 `conversation.title` 的消费保证；失败路径没有 optimistic title 写入。消息、会话 ID、参与者、Agent profile 与 Session 均未被改名代码修改。`title_is_custom` 不进入 DTO；普通 external reuse 和唯一索引竞争恢复使用相同 SQL 保护；旧库重复初始化保持原 title 并补默认 0 标记。

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 私聊省略号菜单容纳重命名与原 Agent 配置，无 Agent 时只显示重命名；群聊保留既有入口 | 是 | `message-pane.tsx:792-809`; `direct-conversation-menu.tsx:62-89`; `chat-workspace-page.tsx:1204-1211` |
| UI、conversations.list 与 Inbox describe 使用既有 `conversation.title` | 是 | `message-pane.tsx:792`; `chat-workspace-page.tsx:921-926`; `work_conversations.py:67-79`; `:104-124` |
| direct 手动标题优先于外部正常同步和竞争恢复，旧库幂等增列，group 行为不变 | 是 | `db.py:34-38`; `:501-504`; `conversations.py:237-251`; `:333-370`; `:397-433` |
| 轻量表单复用既有 PATCH，空白/保存中/失败/焦点/会话切换状态符合约束 | 是 | `direct-conversation-menu.tsx:11-59`; `:62-117`; `message-pane.tsx:792-794` |

架构自洽：改动仅在 IM 内扩展既有 PATCH、repository、query 与前端状态，没有引入 IM→agent 依赖、跨机直读或平行标题机制。注释、公开 Python API 与错误处理沿用现有模式。

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| 私聊菜单与配置动作；桌面/手机 | R1 | `message-pane.tsx:792`; `direct-conversation-menu.tsx:62-89` | `M1-impl/progress.md`; `output/direct-chat-rename/{desktop-menu-final.png,mobile-menu.png}` | covered |
| 改名、取消、空白、保存失败；桌面/手机 | R2 | `direct-conversation-menu.tsx:47-59`; `:91-110` | `M1-impl/progress.md`; `output/direct-chat-rename/{mobile-saved.png,failure-final.png,live.json}` | covered |

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

- **W1 — 两条受影响的 workspace integration 测试仍要求旧的直接 Config 按钮，导致当前前端门禁失败。** `src/IM/frontend/src/features/chat/chat-workspace.integration.test.tsx:1671-1687` 与 `:2097-2106` 在新产品正确呈现 `Conversation menu` 时仍用 `/Config/i` 查找顶层按钮。把两条用例改为先点击 `Conversation menu`，再点击菜单项 `Agent configuration`，并保留各自的 Node chip、导航和“不打开 Group settings”断言；不要恢复 design 已明确替换的旧直接入口。独立复现命令：`./node_modules/.bin/vitest run src/features/chat/components/direct-conversation-menu.test.tsx src/features/chat/chat-workspace.integration.test.tsx -t 'private conversation menu|R7-5|feat-438: direct-agent'`，结果 4 passed、2 failed。

### SUGGESTION（可以修）

None.
