# feat-340-M18 — Progress

post-acceptance fix round 9 (final) — 3 issues 同根:R9-1 agent IM user bootstrap / R9-2 Open chat ↗ 静默 / R9-3 用户消息未乐观渲染。

## R1 — 后端 agent 注册同步建 IM users 行 + GET lazy 补齐 (R9-1)

- Context: R9 final 验:`POST /im/v1/nodes/{id}/agents` 创建 agent profile 但**没建** IM `users` 表行,导致 `GET /im/v1/agents` 的 `user_id` 字段为 null;后续 `POST /im/v1/conversations { participant_ids: [agent.user_id] }` 因 unknown user 报 400;用户无法和新建 agent 私聊。M17 R8-2 只加了 read 侧 lookup,write 侧没补齐。
- Decision:
  1. `IM.application.config_service.ConfigService` 注入 `UserRepository`,新增 `ensure_agent_user(agent_id, display_name)` 方法 — username 规则 `agent:<agent_id>`,已存在则返回,不存在则建。
  2. `create_profile` 在写完 profile 后调 `ensure_agent_user`,保证 create 路径同事务建 user 行。
  3. `to_agent_summary_response`(GET 路径)改为调 `ConfigService.ensure_agent_user`,使预先存在的 legacy seed(无 user 行)在第一次 read 时 lazy 自愈;旧的 user_service.lookup-only 保留为兼容路径。
  4. `deps.get_config_service` wire 上 `users` 依赖。
- Rationale: 单点修在 application 层 — 任何走 ConfigService 的入口(HTTP / WS / future cron)都自动覆盖;避免在 routes 层洒 helper 调用。Lazy bootstrap 兼容 r8alpha seed 数据无需运维迁移。
- Evidence:
  - Tests: `tests/im_service/integration/test_m18_agent_user_bootstrap.py` 2/2 GREEN(create 路径 + legacy seed 路径)。`test_agent_config_api.py` / `test_agent_create_flow.py` 12/12 GREEN(R8-2 加 user_id 字段后 expected dict 已对齐)。
  - Entry: 现有 fastapi TestClient 集成测试已覆盖 POST/GET 真实链路(register → POST agent → GET agents → user_id != null)。
  - Visual/Interaction: N/A(纯后端)。
- Side effect: `tests/im_service/_auth_helpers.py::seed_user_under_owner` 对 `agent:` 前缀的 username 做 idempotent 兼容 — 因 lazy bootstrap 抢先建 user 行,后续 fixture 重复建会 UNIQUE 冲突。改为 lookup 先于 create。
- Out-of-unit:发现 `tests/im_service/integration/test_m103_im_gateway_e2e.py` 和 `test_m136_group_chat_flow.py` 共 8 测试在 base branch 即 fail (`_FakeKernelClient` 缺 submit_message)。立 issue [#2](https://github.com/Mrchen116/nano-multiagent/issues/2),不在 M18 范围。
- Rollback: `git revert 5709e743`
- Commits: C1=b8886569, C2=5709e743

## R2 — 前端 detail page Open chat ↗ 绕开 ensureBootstrap + inline error (R9-2)

- Context: Agents 详情 Open chat ↗ 在 fresh 旅程下完全静默失败(已 4 轮未修)。根因:`createDirectConversation(im-chat-api)` → `ensureBootstrap` → `listUsersRaw` → `GET /im/v1/users` **404**(后端无此端点);mutation `onError` 把错误 setState 但 UI 不显著 → 用户感知"按钮坏了"。
- Decision:
  1. `im-chat-api.ts` 新增 `createDirectChatByAgentUserId({ agentId, agentUserId, agentDisplayName })` 函数 — 用 auth store 拿 selfUserId,直接 POST /conversations { participants, participant_ids: [self.id, agent.user_id] };**不走 ensureBootstrap / listUsersRaw**。
  2. `im-chat-api.ts` 新增 `listAgents` export(`listAgentsRaw` 的薄包装),给详情页用以获取 user_id。
  3. `chat-api.ts` 把两者按 mock/im 模式分流暴露。
  4. `agent-detail-page.tsx`:加 `agentsSummaryQuery`(`["settings","agents","summary"]`)拿 agent.user_id;`openDirectChatMutation.mutationFn` 切到新函数;mutation 失败时渲染 `data-testid="open-chat-error"` 红色 banner(role="alert", aria-live)。
  5. 旧 `createDirectConversation` 不动(其他流程仍用 — group / fresh-direct);只是 detail page 不再调它。
- Rationale: R9-1 落地后 agent.user_id 已可信,直接拿来用即省一跳 ensureBootstrap 也避免 404 路径;新函数边界清晰,不污染老的 mock 兼容层。inline error banner > toast — 详情页本身有 errorMessage state + footer,banner 在 button 附近更易看到。
- Evidence:
  - Tests: `agent-detail-page.test.tsx` 3/3 GREEN — 含 R9-2 "surfaces inline error when open-chat fails" 和"调用 createDirectChatByAgentUserId 而非 createDirectConversation"两断言。
  - Entry: vitest workspace 集成测试全绿(140/140 chat 测试)。
  - Visual/Interaction: 单测层模拟点击 + 验证 DOM 元素 `data-testid="open-chat-error"` 出现 + textContent 含错误。完整浏览器视觉旅程留给 reviewer R10。
- Rollback: `git revert 68559d96`
- Commits: C1=cae56a8b, C2=68559d96

## R3 — chat-workspace 发消息后乐观渲染用户气泡 (R9-3)

- Context: R9 验:在已开私聊对话内,用户发送一条新消息后,**自己的用户气泡未在主消息 pane 立即渲染**(侧栏 preview 已更新;DB 已有 record;agent 后续回复气泡正常)。reducer 已有 dedupe by message_id(line 64 — M17/R8-1 引入),所以乐观插入安全。
- Decision:
  1. `chat-workspace-page.tsx::streamReducer` 加 `append_optimistic` action type — 校验 conversation_id 匹配 + by id dedupe → append message。
  2. `sendMutation.onSuccess` 拿到 server 返回的完整 `Message`(含真实 id / created_at)→ `dispatch({ type: "append_optimistic", message })`;reducer 对未来的 WS `message.created` 同 id echo 已 dedupe 不重复。
  3. 既有 "drops an image..." 集成测试因新行为(message 内 attachment img 出现在主 pane)断言失败 — 改为 scoped 查 composer chip strip 内的 img 是否清空,而非全文档,这正确表达 product intent。
- Rationale: server 已返完整 Message → 直接 dispatch 比手工合成 optimistic id 更安全(无需考虑 conv_id / sender 字段同步)。Reducer dedupe 已 production-grade。
- Evidence:
  - Tests: `chat-workspace.integration.test.tsx::R9-3` GREEN — 验"发送后 'Say hello briefly' 立即出现"+ "后续 WS echo 同 id 不重复"。全 7 workspace 集成测试 GREEN。
  - Entry: 浏览器旅程未在 worker 阶段执行(IM service 当前由 team-lead 跑在 main repo,worker 不重启服务);build + bundle 含 `append_optimistic` string。
  - Visual/Interaction: vitest jsdom 层验证完整,真实视觉 viewport 测试留给 reviewer R10。
- Rollback: `git revert aec480e8`
- Commits: C1=c63d1328, C2=aec480e8

## R4 — IM-SPEC.md 同步 + frontend build

- Context: spec 缺"agent 注册同步建 IM user 行"契约段;R9-1 引入的 invariant 需文档化避免后续 worker 误删。
- Decision: `docs/IM-SPEC.md` §7.4 "节点下创建 Agent" 流程补一行 "IM 服务同步建对应 IM users 行";新增 §7.5 "Agent ↔ IM users 行的同步契约 (feat-340-M18 R9-1)" 详写 username 规则、生成时机、历史兼容路径、不变量、响应字段示例。
- Rationale: invariant 入 spec 而非 progress — orchestrator 派下一波 worker 时只读 SPEC + design.md,这条规则必须在 SPEC 找得到。
- Evidence:
  - Build: `cd src/IM/frontend && npm run build` 成功(179 modules, 497kB main chunk)
  - Bundle: `grep -oE "open-chat-error|append_optimistic" dist/assets/*.js` 都命中 → 关键修复进 production bundle
  - Tests: backend M18 范围 12/12 GREEN;frontend 250/250 GREEN
- Rollback: spec 段独立,直接 git revert 即可
- Commits: (随 R4 docs commit 一起)

## 端到端浏览器旅程

worker 阶段不重启 main repo 在跑的服务以免污染 team-lead 工作流;完整旅程交给 R10 reviewer 在派发时统一跑(他们会自己起 staging 服务 + 走完整旅程截图)。
worker 已提供:
- 单元/集成测试覆盖每个 R 的 happy + error 路径
- frontend build 成功 + bundle 含修复关键字
- 设计意图与 invariant 入 IM-SPEC.md

## Out-of-unit Issue

- [#2 — _FakeKernelClient missing submit_message](https://github.com/Mrchen116/nano-multiagent/issues/2) — 8 个 integration test 在 base 已 fail,与 M18 无关。
