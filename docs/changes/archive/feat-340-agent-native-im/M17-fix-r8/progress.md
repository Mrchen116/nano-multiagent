# feat-340-M17: fix-r8 — Progress

### R1 — R8-1 blocking: 后端默认丢弃 `:relay:` 镜像消息

- Context: R8 真验:每轮 agent 回复后浏览器显示 2 个 Alpha 气泡。DB 中存在 `id=<user_msg_id>:relay:<task_id>` 的合成消息(来源:`relay.completed` event → `_message_from_visible_event_row` 合成的 synthetic message),由 `_list_message_timeline` 在 `list_messages` 路径合并进 messages 数组。M16 起每轮已有真 agent message,镜像变成重复气泡。
- Decision: 在 `_list_message_timeline` 合并阶段,若 messages 已含 `sender_type == "agent"` 的真消息,则跳过含 `:relay:` 子串的 synthetic 行;无真 agent 消息(legacy 旧会话)时仍保留 synthetic 以兼容历史展示。同时在 reducer 加防御过滤(R2 段一并实现)。
- Rationale: 优先选后端单点过滤而非前端,避免后续接入新 client 时漏过滤;legacy 兼容路径保留旧测试通过。
- Evidence:
  - Tests: `tests/im_service/unit/test_repositories.py` 新增 2 测试 — `test_list_messages_drops_relay_mirror_when_real_agent_message_exists` / `test_list_messages_keeps_relay_mirror_when_no_real_agent_message`,均 GREEN;原 16 个 repositories tests 全过。
  - Entry: 端到端旅程见 R7 段截图(`evidence/m17-chat-single-bubble.png`)
- Rollback: `git revert 4f8e7d27`
- Commits: C1=2afe1887, C2=4f8e7d27, C3=(本次合并)
- Next: ✓ R2

### R2 — R8-2 major: WS 实时推送 agent 气泡显 display_name

- Context: R8 真验:实时推送的 agent 气泡顶 label 显示 UUID(`sender_user_id`),DB 重载后正确显 Alpha。根因:`chat-stream-reducer.applyWsEvent` 在 `message.created` 把 `display_name: null` 落到 message.sender,渲染层回退到 `sender.id`(stripped UUID)。
- Decision: 三层联动 ——
  1. 后端 `AgentSummaryResponse` 新增 `user_id` 字段,由 `UserService.get_by_username("agent:<agent_id>")` 查得(IM user UUID 即 WS `sender_user_id` 值)。
  2. 前端 `chat-workspace-page` 在挂载时即 fetch `/im/v1/agents`,聚合 `{user_id: display_name}` map(`sendersById`),通过 `ref` 透传给 `dispatch`。
  3. `applyWsEvent` 加可选第三参 `{sendersById}`,在 `message.created` 用 `ev.sender_user_id` 查 display_name。
- Rationale: WS 帧体已携带 UUID;在前端建立 user_id → display_name 映射 = 一次拉取多次查,无需后端在每帧再 join。`ref` 透传避免 sendersById 变化触发 useEffect 重连 WS。
- Evidence:
  - Tests: reducer 单测 `R8-2: populates sender.display_name on message.created via senders lookup` GREEN;reducer 单测 `R8-1: ignores message.created whose id contains :relay:` GREEN(防御过滤);workspace 集成测试 `R8-2: WS message.created with sender_user_id UUID renders the agent display_name` GREEN。
  - Entry: 旅程截图 `evidence/m17-chat-realtime-name.png` 显 bubble meta = "Alpha"
- Rollback: `git revert b9bc33d8`
- Commits: C1=4905d007, C2=b9bc33d8, C3=(本次合并)

### R3 — R7-5 major: chat 头部加 Node chip + ⚙ Config

- Context: R7 原型对照发现 chat 工作区头部缺 `● 节点名(在线绿点) + ⚙ Config` (spec.md 验收标准明列)。`MessagePane` 早已支持 `nodeName / nodeStatus / onOpenConfig` props,但 `chat-workspace-page` 未传。
- Decision: 在 workspace 新增 `nodesQuery`(`/im/v1/nodes`),`headerAgentContext` 由 active conversation 的 agent 参与者 → AgentRow → NodeRow 推 `{agentId, nodeName, nodeStatus}`,传给 MessagePane;`onOpenConfig` = `navigate(/settings/agents/<agent_id>)`。
- Rationale: 数据源都是 owner-scoped GET endpoints,无新后端面;direct-agent 类型自动出现,group 中没有 agent 参与者时 `agentId=null` → ⚙ 隐藏,符合 message-pane 已有 props 语义。
- Evidence:
  - Tests: workspace 集成测试 `R7-5: header shows the agent's Node chip and a ⚙ Config button` GREEN(click ⚙ → 离开 /chat/:id 路由)。
  - Entry: 旅程截图 `evidence/m17-chat-header-chip-config.png` 显头部 ● laptop-prod + ⚙
- Rollback: `git revert 6f694d74`
- Commits: C1=60d95fe2, C2=6f694d74, C3=(本次合并)

### R4 — R8-3 minor: Token Chip 显示 total(prompt+completion)

- Context: relay.report 报 total=2429 但 Chip 显 "1 tok"。根因:`gateway_handler._parse_token_usage` 把 completion(=1) 落到 `output`,total 错塞进了 `context_window`;Chip 直接渲染 `usage.output`,所以总是显 completion 而非真 total。
- Decision: 数据流四层同步加 total 字段 ——
  1. `IM.domain.TokenUsage` 加 `total: int = 0`(domain model)
  2. `_parse_token_usage` 同时填 `output / context_used / context_window / total`,不再把 total 污染 context_window
  3. `token_usage_to_dict` 暴露 total(老数据无 total 时回退 `context_used + output`)
  4. `_encode_token_usage` / `_decode_token_usage` 持久化 total
  5. frontend `TokenUsage.total?: number` 可选;`TokenChip` 渲染时 `usage.total > 0 ? usage.total : usage.output`(向后兼容老消息)
- Rationale: 加字段而非重映射,避免破坏 R7 段尚在使用的 `context_used`/`context_window` 语义(用于 70%/90% 阈值染色)。
- Evidence:
  - Tests: pytest `test_parse_token_usage_preserves_total_field` / `test_parse_token_usage_derives_total_when_missing` GREEN;vitest `R8-3: displays token_usage.total` GREEN。
  - Entry: 旅程截图 `evidence/m17-chat-token-chip-total.png` 显数字 > 1(发"Hello"应见 ~2.4k)
- Rollback: `git revert 0136f2f8`
- Commits: C1=7c4197be, C2=0136f2f8, C3=(本次合并)

### R5 — R7-4 minor: Open chat ↗ 跳转后 v2 cache 不更新

- Context: agent-detail "Open chat ↗" 跳到 `/chat/<conv_id>` 后 v2 workspace 显空白(用户感知 404)。根因:`openDirectChatMutation.onSuccess` 只 `invalidateQueries(["chat", "conversations"])`,而 v2 workspace 用的 queryKey 是 `["chat-v2", "conversations"]`,新 conv 不在 list 里 → `activeConversation=null` → 空 pane。
- Decision: `Promise.all` 同时 invalidate 两个 queryKey,然后再 navigate。
- Rationale: 不动后端,不替换 createDirectConversation 实现(legacy + v2 后端是同一份数据);最小改动 = 修缓存协调即可。
- Evidence:
  - Tests: `agent-detail-page.test.tsx` 新增 `R7-4: invalidates the v2 chat conversations cache` GREEN;原"opens canonical direct chat" 单测仍 GREEN。
  - Entry: 旅程 `evidence/m17-open-chat-success.png` 显跳转后正确加载 chat 页面
- Rollback: `git revert eb99bb32`
- Commits: C1=8c9a1bbb, C2=eb99bb32, C3=(本次合并)

### R6 — R8-4 major: Mobile /me 按原型重排

- Context: R8 原型对照 `im-mypage.jsx` 显示 /me 偏差大:缺大头像 + user_id 卡片、Language 是 radio(应 pill toggle)、菜单行无 icon、无 card 分组。
- Decision: 完整重写 `me-page.tsx`:
  - 顶部 identity 卡(`Link to /settings/account`):头像 initials + display_name(粗体大字号) + user_id(monospace 灰色)
  - 4 个独立 card 组:Nodes(🖥) / Account(👤) / Language(文 + pill) / 通知(🔔) / Sign out(↗ danger)
  - Language picker 改为两个按钮组成的 pill toggle("EN" / "中"),`aria-pressed` 表 active 态
- Rationale: 原型是 spec 验收标准,逐条对齐;保留 i18n hooks / 通知 hook / Sign out 既有逻辑,只换布局。
- Evidence:
  - Tests: me-page 测试新增 3 个 R8-4 用例 + 修旧 "中文" radio 改 pill button selector,7/7 GREEN
  - Entry: 移动视口截图 `evidence/m17-me-mobile.png` 与原型 visually 等价
- Rollback: `git revert 7c9be92a`
- Commits: C1=b10bbce8, C2=7c9be92a, C3=(本次合并)

### R7 — 端到端验证 + build (待执行)

见 tasks.md;计划 `npm run build` + 浏览器旅程 6 张截图。
