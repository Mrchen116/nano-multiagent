# feat-340-M17: fix-r8 (relay 重影 / 实时 UUID label / 头部缺 chip+⚙ / /me 偏 / Open chat 404 / Token Chip 字段错) — Tasks

> 对齐: ../design.md M17 行(2026-05-12 立项)

## 目标

R8 真验暴露的 1 blocking + 3 major + 2 minor 全部修复;Round 9 acceptance 在 fresh dist + 真服务实例下复现 R8 旅程不再出现 R8-1~R8-4 / R7-4 / R7-5 现象,且与原型对照不"偏"。

## 退出标准

- [ ] R8-1 — 同一回合不再出现 2 个 Alpha 气泡(后端 / 前端 二选一过滤 `:relay:` 镜像)
- [ ] R8-2 — WS 实时推送的 agent 气泡顶 label 显 "Alpha"(display_name),非 UUID
- [ ] R7-5 — Chat workspace 头部含 Node chip(● 节点名,在线绿点) + ⚙ Config 按钮(跳 `/settings/agents/{agent_id}`)
- [ ] R8-4 — Mobile `/me` 与原型 `im-mypage.jsx` 视觉等价:user 卡片(大头像 + user_id) / Language pill toggle / 菜单行带 icon + 分组卡片
- [ ] R7-4 — agent-detail 的 "Open chat ↗" 跳转后不再出现 404 / 空白页
- [ ] R8-3 — Token Chip 显示 token_usage 真实 total(>1),非 completion=1
- [ ] vitest + pytest 全绿
- [ ] `cd src/IM/frontend && npm run build` 成功;dist/assets/*.js grep 含修后特征

## 测试策略

- 后端(R8-3 一项可能涉及):pytest `tests/unit/IM/test_*` — 增 `_parse_token_usage` total 映射用例。
- 前端组件:
  - R8-1 reducer 测试 — `applyWsEvent` 对 `:relay:` 后缀 message_id 不入 messages 列表
  - R8-2 reducer 测试 — `message.created` 含 agents map 查 display_name
  - R7-5 message-pane / workspace 测试 — passing onOpenConfig + nodeName 时 header 渲染 ⚙ + Node chip
  - R8-3 token-chip 测试 — 显示 total
  - R8-4 me-page 测试 — 含 user_id、Language pill、icon 行
- 入口验证:浏览器跑 R8 同旅程(home → chat → 发 "Hello" → 截图 5 项 + /me 移动 + Open chat),evidence 存 `M17-fix-r8/evidence/`
- 前端 `npm run build` + grep dist bundle 验证

## Roadpoints

### R1 — R8-1: 过滤 `:relay:` 镜像消息(后端默认排除)

- 步骤: `IM/infra/repositories.py` `list_messages` / `list_visible_messages` 路径里把 `_message_from_visible_event_row` 的 `relay.completed` 那条不再 upsert 进 messages(或仅在没有对应真 agent 消息时降级填充)。前端 reducer 同步加防御过滤 `:relay:` id。
- 验证: 单测 `test_messages_endpoint_excludes_relay_mirrors`;reducer 单测 `ignores message.created with :relay: suffix`(虽然 WS 不发,防御);E2E 浏览器 chat 内单 Alpha 气泡。

### R2 — R8-2: WS 实时 agent 气泡显 display_name

- 步骤: chat-stream-reducer 接受 agents map(`{user_id: display_name}`),`message.created` 时 lookup;workspace 把 react-query agentsQuery 数据 + `/im/v1/users/{id}` 或 agent.user_id 映射传入。
- 验证: reducer 单测 `populates display_name from agents map`;E2E 实时 turn 截图 sender 名是 "Alpha"。

### R3 — R7-5: chat 头部 Node chip + ⚙

- 步骤: `chat-workspace-page.tsx` 拉 `/im/v1/nodes` + `/im/v1/agents`,根据 active conversation 的 agent participant 找 agent.node_id → node.node_name + node.status;传入 MessagePane `nodeName / nodeStatus / onOpenConfig`(`navigate(/settings/agents/{agent_id})`)。
- 验证: workspace 集成测试断言 header 渲染 ● Node chip + ⚙ 按钮;⚙ click → navigate 到正确路径。E2E 截图。

### R4 — R8-3: Token Chip 显示 total

- 步骤: `chat-types.ts` TokenUsage 加可选 `total`;`event_types.py token_usage_to_dict` 输出 total;`_decode_token_usage` 读 total;`_parse_token_usage` 保留 total;`TokenChip` 渲染优先 total(回退 output 用于旧数据)。
- 验证: pytest `test_parse_token_usage_preserves_total` + frontend token-chip 单测 `displays total when provided`。E2E Chip 显 > 1。

### R5 — R7-4: Open chat ↗ 跳转

- 步骤: 用 v2 `createConversation`({title, agentIds:[agentId]})替换 agent-detail 的 legacy `createDirectConversation`,确保 v2 list 能立刻 includes;invalidate `["chat-v2","conversations"]`。
- 验证: agent-detail 单测验 click 后 navigate("/chat/<id>") + v2 invalidate。E2E 点击 Open chat 进入正常 chat 页(标题=agent 名,可发消息)。

### R6 — R8-4: Mobile /me 重排

- 步骤: 按 `im-mypage.jsx` 重写 `me-page.tsx`:user 卡片(大头像 + display_name + user_id mono) / Nodes 行 icon=🖥 + 数量 sub / Account 行 icon=👤 / Language 行 pill toggle / Sign out 行 icon=↗ + danger 色。每组 cardStyle marginTop=14。
- 验证: me-page 单测 `renders user_id mono` / `renders language pill toggle` / `renders rows with icons`。E2E 移动视口截图与原型对照。

### R7 — 端到端验证 + build

- 步骤: `cd src/IM/frontend && npm run build`;启 3 服务;浏览器跑旅程截 6 张图。
- 验证: 6 张 evidence 截图 + grep dist。
