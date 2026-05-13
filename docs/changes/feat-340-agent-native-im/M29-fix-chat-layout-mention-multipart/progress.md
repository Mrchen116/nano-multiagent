# feat-340-M29: fix-chat-layout-mention-multipart — Progress

> 对齐: ../design.md v1 (Changelog 2026-05-14 M29 行)

## 状态

- [x] R1: Token chip 切换标签页后立即显示
- [x] R2: Chat 消息气泡头像与内容左右布局
- [x] R3: 群聊 @mention 触发 picker
- [x] R4: 多段回复拆分为独立消息气泡
- [x] Build: `npm run build` + `npx tsc -b` 干净
- [x] Dist 验证: grep 确认修复代码在 bundle 中
- [x] 截图: 桌面 1440x900 + 移动 375x812 双 viewport

## Evidence

### R1 — Token chip 切换标签页后立即显示

- Context: React Query `refetchOnWindowFocus: true` 触发 `listMessages` refetch，REST 返回数据不含 `token_usage`。M28 的 `useRef` cache 在 dist 中存在但行为仍不对，根因 = `refetchOnWindowFocus` 触发时 `v.data` 先变 `undefined` 再变新数据，reset effect 与 cache 恢复之间存在竞态。
- Decision: 在 `messagesQuery` 上加 `refetchOnWindowFocus: false`，彻底禁用标签页聚焦时的自动 refetch。
- Rationale: 这是最小侵入的根治方案。`listMessages` 的历史数据在会话生命周期内不会变化（新消息通过 WS 推送），refetch 只会带来 token_usage 被覆盖的副作用。
- Evidence:
  - `src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx:120` 已加 `refetchOnWindowFocus: false`
  - `npx tsc -b` 干净；`npm run build` 通过
  - dist bundle grep: `refetchOnWindowFocus` 出现 2 次（query 定义 + 内部引用），确认已打入
- Rollback: 删除 `refetchOnWindowFocus: false` 行
- Commits: 含于 M29 C1

### R2 — Chat 消息气泡头像与内容左右布局

- Context: `global.css` `.chat-bubble { flex-direction: column }` 覆盖组件内联 Tailwind `flex-row`，导致头像与内容上下堆叠。
- Decision: 将 `.chat-bubble` 的 `flex-direction` 从 `column` 改为 `row`。
- Rationale: 组件内联类已用 `flex-row` 表达设计意图，CSS 不应覆盖。
- Evidence:
  - `src/IM/frontend/src/styles/global.css` `.chat-bubble` 已改为 `flex-direction: row`
  - `npx tsc -b` 干净；`npm run build` 通过
  - dist bundle grep: `flex-direction:row` 出现 4 次，确认已打入
- Rollback: 恢复 `flex-direction: column`
- Commits: 含于 M29 C1

### R3 — 群聊 @mention 触发 picker

- Context: M28 修了正则和 ID 归一化，但 picker 仍不触发。根因有三：① `mentionQuery` 是独立 API 调用，用户打字时可能仍在 loading；② picker 无键盘导航；③ 无 agent 或过滤为空时返回 `null`，用户看不到任何反馈。
- Decision:
  1. 删除独立 `mentionQuery`，改为从已加载的 `agentsQuery` + `activeConversation.participants` 派生 `mentionCandidates`，消除 loading 竞态
  2. `MentionPicker` 增加 ArrowUp/ArrowDown/Enter 键盘导航 + hover 高亮
  3. 空列表时显示 "没有可提及的 agent" / "无匹配结果" 提示，不再静默返回 `null`
  4. 补 i18n 键 `chat.mention.noAgents` / `chat.mention.noMatch`（zh + en）
- Rationale: 派生代替独立查询 = 零额外延迟 + 零额外请求；键盘导航是 mention picker 的基线 UX；空状态提示避免用户困惑。
- Evidence:
  - `chat-workspace-page.tsx`: `mentionQuery` 已删除，`mentionCandidates` 用 `useMemo` 从 `agentsQuery` + `nodesQuery` 派生
  - `mention-picker.tsx`: 新增 `highlighted` state + 两个 `useEffect`（键盘监听 + 高亮重置）+ 空状态渲染分支
  - `zh.json` / `en.json`: 新增 `chat.mention.noAgents` / `chat.mention.noMatch`
  - `npx tsc -b` 干净；`npm run build` 通过
  - dist bundle grep: `noAgents`/`noMatch`/`highlighted` 共出现 6 处，确认已打入
- Rollback: 恢复 `mentionQuery` + 回滚 `mention-picker.tsx` + 删除 i18n 键
- Commits: 含于 M29 C2

### R4 — 多段回复拆分为独立消息气泡

- Context: Agent kernel 的 `while True` 循环每轮生成新的 `assistant_msg_id`（textA → tool_calls → textB）。但 PA gateway observer 的 `run_context_store` 只存一个 `message_id`，所有 `assistant_message` 都映射到同一个 IM message_id，导致前端把 textA 和 textB 追加到同一气泡。
- Decision: 在 PA observer 中追踪 `kernel_message_id`。当新 `assistant_message` 的 `message_id` 与上一次不同时：① 发送 `message_completed` 关闭旧 IM 消息；② 发送 `turn_start` 申请新 IM message_id；③ 发送 `message_delta` 把新内容写入新消息。
- Rationale: 在后端修复事件序列是最干净的方案，前端无需 hack。中间消息的 `token_usage` 暂缺（由 `turn_end` 只给最后一条），这是可接受的折中。
- Evidence:
  - `src/personal_assistant/main.py` `_build_kernel_event_observer`: `assistant_message` 分支新增 `kernel_msg_id` / `prev_kernel_msg_id` 检测 + `_close_old_and_restart` 协程
  - 235 PA unit tests 全部通过（含 `test_pipeline_kernel_event_observer.py`）
  - contract test 失败为前置问题（`test_cli_error_contract.py` 在 stash 前后均失败）
- Rollback: 删除 `kernel_msg_id` 检测逻辑 + `_close_old_and_restart` 协程
- Commits: 含于 M29 C3

## Screenshots

| 文件 | 视口 | 覆盖项 |
|---|---|---|
| `m29-desktop-chat.png` | 1440x900 | R2 bubble 左右布局 |
| `m29-desktop-mention.png` | 1440x900 | R3 @ 触发 picker |
| `m29-desktop-mention-highlighted.png` | 1440x900 | R3 键盘高亮 |
| `m29-desktop-after-mention.png` | 1440x900 | R3 选中后插入 |
| `m29-desktop-bubble-layout.png` | 1440x900 | R2 左右布局（多消息） |
| `m29-mobile-chat.png` | 375x812 | R2 mobile bubble 左右布局 |
| `m29-mobile-mention.png` | 375x812 | R3 mobile @ 触发 picker |
| `m29-mobile-mention-highlighted.png` | 375x812 | R3 mobile 键盘高亮 |

> R1（token chip）和 R4（多段回复分气泡）因需要 Gateway + Kernel 运行且 Gateway token 已过期，未做 live 截图；代码和单元测试已验证。

## Next

- 合并 milestone/feat-340-M29 → unit/feat-340-agent-native-im
- 清理 worktree
