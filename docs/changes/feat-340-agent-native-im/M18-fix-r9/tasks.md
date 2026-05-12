# feat-340-M18: fix-r9 (agent IM user bootstrap + open-chat 调用链) — Tasks

> 对齐: ../design.md Milestone 表 M18 行

## 目标

闭合 R9 final 验收暴露的 3 个 issue:

- (R9-1 blocking) 新建 agent 后,`/im/v1/agents` 返回的 `user_id` 不再为 null;后续 `POST /im/v1/conversations { participant_ids: [agent.user_id] }` 成功 201。
- (R9-2 blocking) Settings → Agents 详情页 Open chat ↗ 不再静默失败:点击后跳 `/chat/<conv_id>` 并 main pane 加载消息列表;失败路径有显式错误反馈。
- (R9-3 minor) 用户在主 pane 发消息后,立即看到自己的气泡,无需等待 WS 回放。

## 退出标准

- [x] POST `/im/v1/nodes/{node_id}/agents` 同事务在 IM `users` 表建 `username=agent:<agent_id>` 行;响应 + 后续 GET `/im/v1/agents` 返回 `user_id != null`
- [x] 已存在的 agent(无 user 行)在 GET `/im/v1/agents` 路径上 lazy 自动补齐(兼容 r8alpha seed)
- [x] `docs/IM-SPEC.md` 加段"agent 注册时同步建 IM user 行"契约
- [x] `agent-detail-page.tsx::openDirectChatMutation` 不再走 `ensureBootstrap` / `listUsersRaw`,直接用 `POST /conversations { participant_ids: [agent.user_id] }`
- [x] mutation onError 显式 inline error banner(`data-testid="open-chat-error"`),不再静默
- [x] `chat-workspace-page` 发送 POST 成功后乐观 append 用户气泡,WS message.created 时按 id 去重
- [x] `cd src/IM/frontend && npm run build` 成功 + grep dist/assets 验关键修复进 bundle
- [ ] 浏览器端到端旅程: 注册→新建 agent→Open chat↗→发消息→看 streaming→刷新→Open chat 再点 → 全过 (留给 R10 reviewer 验)

## 测试策略

| 改动点 | 测试 |
|---|---|
| R9-1 后端 create 路径 | pytest `tests/im_service/api/test_nodes_routes.py` 新增"POST agent 同时建 user 行 + 响应 user_id != null" |
| R9-1 后端 GET lazy 兼容 | pytest 新增"GET /im/v1/agents 对已存在 agent 但无 user 行,lazy 建 + 返 user_id != null" |
| R9-2 前端 mutation | vitest `agent-detail-page.test.tsx` 新增"Open chat ↗ 用 agent.user_id 走 POST /conversations,不调 /im/v1/users" |
| R9-2 onError | vitest "createDirectConversation 失败时显示错误 toast" |
| R9-3 乐观渲染 | vitest `chat-workspace-page.test.tsx` 新增"POST 成功后立即出现用户气泡;WS message.created 同 id 不重复" |
| 真实入口(必做) | 三服务起来 + Playwright/手测旅程 + 截图 6 张 |

## Roadpoints

### R1 — 后端: agent 注册同步建 IM user 行 + GET lazy 补齐

- 步骤:
  1. 在 `IM.application.config_service.ConfigService.create_profile` 注入 `UserRepository`(或专用 UserService),create 完 profile 后,若 `users.get_user_by_username("agent:<agent_id>") is None`,调 `users.create_user(username=f"agent:{agent_id}", display_name=agent.display_name)`。
  2. `agents.py::to_agent_summary_response` 已 lookup user_id;在 lookup miss 时也 lazy create(以兼容 r8alpha seed 已存在的"裸 agent")。
  3. `nodes.py::create_node_agent` 路径不动(因为它调用 ConfigService.create_profile,会经新逻辑)。
  4. 添加 contract test 保证响应里 user_id != null。
- 验证:
  - pytest 全绿
  - curl POST /im/v1/nodes/{node}/agents → 返 user_id != null
  - curl GET /im/v1/agents → 所有 agent user_id != null

### R2 — 前端: detail page Open chat ↗ 直走 user_id + toast 反馈

- 步骤:
  1. `agent-detail-page.tsx`:在 component 内 fetch `/im/v1/agents` 拿当前 agent 的 user_id(detailQuery 用的是 config,不带 user_id;另起一个 `useQuery(["settings","agents","summary"])` 或扩展 detailQuery)。
  2. `openDirectChatMutation.mutationFn` 改成调用一个新的 `createDirectChatByUserId({ userId, title })` 函数;该函数直接 `POST /im/v1/conversations { title, participants: [{type:"user",id:self.id},{type:"agent",id:agent.agent_id,display_name}], participant_ids: [self.id, agent.user_id] }`;**不走 ensureBootstrap / listUsersRaw**。
  3. `onError` 写显式 inline error block(detail page 已有 errorMessage state — 加 prominent aria-live 错误带 `data-testid="open-chat-error"`)。
  4. 保留 R7-4 的 v2 cache invalidate。
- 验证:
  - vitest agent-detail-page.test 不出 `/im/v1/users` 调用
  - 浏览器: Open chat ↗ 跳成功 + 失败 case 显错误

### R3 — 前端: chat-workspace 发送消息后乐观渲染

- 步骤:
  1. 在 `chat-workspace-page.tsx` 的 `sendMessageMutation.onSuccess` 内,把刚发的用户消息 dispatch 到 reducer(以 server 返回的 `message_id` 为 id),让 reducer append 到当前 conversation 的 messages 数组。
  2. WS `message.created` 时 reducer 已按 id 去重(R8-1 已支持 dedup)— 验证同 id 不重复。
- 验证:
  - vitest workspace test "发送后立即出现 user bubble"
  - 浏览器: 输入消息 → 立即看到气泡

### R4 — IM-SPEC.md 同步 + build + 端到端验证

- 步骤:
  1. `docs/IM-SPEC.md` 加段:"### Agent 注册时同步建 IM user 行(feat-340-M18 闭环)" — 列契约。
  2. `cd src/IM/frontend && npm install --no-audit --no-fund && npm run build`
  3. grep `dist/assets/*.js` 确认关键字符串(e.g. "open-chat-error" data-testid 或 R2 函数名)
  4. 起 IM service + Gateway + LLM proxy(已在),浏览器走旅程 + 截图存 evidence/
- 验证:
  - 6 张截图:r10-01-fresh-register / r10-02-create-agent / r10-03-open-chat / r10-04-streaming / r10-05-refresh-open-chat-again / r10-06-final-state
