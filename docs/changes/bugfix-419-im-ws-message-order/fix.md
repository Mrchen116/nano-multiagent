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

<!-- 实施后回填 -->

## 验证

<!-- 实施后回填 -->
