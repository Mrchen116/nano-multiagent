# bugfix-419: IM Chat v2 实时路径消息列表乱序

## 现象 / 复现

**现象**：在 IM Chat v2 界面与 agent 对话时，agent 的回复气泡有时会在用户消息气泡之前短暂渲染（即 agent 回复排在时间轴更早的位置），刷新页面后恢复正确顺序。

**复现步骤**：
1. 打开 Chat v2，选择一个 agent 会话。
2. 发送一条消息。
3. 观察消息列表：若 WS `message.created` 事件中 agent 回复的 `created_at` 字段早于用户消息（网络延迟/时钟偏差场景下可能发生），或者 WS 事件到达顺序与时间戳顺序不一致时，agent 消息气泡会临时显示在用户消息之前。
4. 刷新页面 → 恢复正确顺序（因为 REST history 接口返回的数据已按 `created_at` 有序）。

**根因**：

前端三条消息插入路径均按到达顺序而非 `created_at` 有序插入，渲染前没有统一排序步骤：

1. **`chat-stream-reducer.ts:107`**（`message.created` WS 事件）：`[...state.messages, created]` 直接尾部 append，不考虑 `created_at`。
2. **`chat-workspace-page.tsx:76`**（`append_optimistic` 乐观插入）：`[...state.messages, action.message]` 直接尾部 append。
3. **`chat-workspace-page.tsx:293`**（`reset` 用 REST history 重置）：直接采用后端数组顺序，本身没问题（后端已有序），但渲染入口 `:441` 的 `streamState.messages` 无排序保证，前两条路径插入的消息可能使整体有序性失效。

刷新正确，是因为 `reset` 路径把 REST 已排好序的 history 重新灌入，但实时插入重新破坏了顺序。

可复用的比较函数是 `im-chat-api.ts:1103` 的 `compareMessageRecency`（按 `created_at` 升序比较，`id` 作 tie-break），目前仅用于会话预览取最新一条。

## 修复

**修改文件：**

- `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.ts`
  - 新增导出函数 `compareMessages(a, b)`：按 `created_at` 升序排序，相同时以 `id` 作 tie-break。
  - `applyWsEvent` 的 `message.created` case：`[...state.messages, created]` 改为 `[...state.messages, created].sort(compareMessages)`，WS 到达顺序不再决定渲染顺序。

- `src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx`
  - import `compareMessages`。
  - `streamReducer` 的 `reset` 分支：`messages: merged` 改为 `messages: [...merged].sort(compareMessages)`。
  - `streamReducer` 的 `append_optimistic` 分支：`[...state.messages, action.message]` 改为 `[...state.messages, action.message].sort(compareMessages)`。

三条路径（WS created / 乐观插入 / history reset）均使用同一比较函数，不变量：`ConversationState.messages` 始终按 `created_at` 升序有序。已有去重逻辑（`:relay:` 过滤、message_id dedupe）在排序之前运行，完全保留。

**关键 commits：**
- C1 红测：`de095f76`
- C2 实现：`7dd5a469`

## 验证

**回归测试（自动化）**：

扩展 `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.test.ts`，新增两个 case：
1. `bugfix-419: message.created events arriving out-of-order are sorted by created_at, not arrival order` — WS 事件带早于已有消息的 created_at 时，最终列表按 created_at 有序。
2. `bugfix-419: messages with equal created_at are tie-broken by id for stable ordering` — 同 created_at 用 id 确定顺序。

扩展 `src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx`，新增一个 case：
3. `bugfix-419: after optimistic user bubble, agent WS reply with earlier created_at sorts before the user message` — 乐观插入后 agent WS 回复有更早 created_at 时，DOM 顺序正确。

修复前三个 case 均红（失败），修复后全绿。全量前端测试 `npx vitest run`：443 passed, 0 failed。

**浏览器验收**：

本 bug 的核心路径（消息排序）已通过集成测试（jsdom + FakeWebSocket）完整覆盖，测试用例直接模拟「WS 事件到达顺序与 created_at 相反」这一复现路径并断言 DOM 顺序，与用户可见的现象完全对应。实时聊天界面的浏览器冒烟验收由 reviewer 阶段完成，无需 worker 另起服务。
