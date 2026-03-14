# M171 Progress — 修复 canonical 运行态 agent 列表为空导致群聊无法创建

## 启动记录
- worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M171`
- branch：`milestone/M171`
- `data/dev-tasks.json` 已确认在 worktree 内指向主仓同一份文件。

## 初始根因判断
- `GET /im/v1/agents` 走的是 `ConfigService.list_runtime_selectable_profiles()` → `AgentProfileRepository.list_runtime_selectable_profiles()`。
- 该 SQL 把可选 runtime agent 限定为：必须 `ap.node_id` 非空、`nodes.owner_id` 非空、且 `(ap.owner_id='' or ap.owner_id = n.owner_id)`。
- fresh canonical runtime 中，gateway `node.register` 会先写入 `nodes` / `agent_profiles`，但此时 node 尚未 bind，因此 `nodes.owner_id=''`；结果是刚注册的真实 agent 被全部过滤掉。
- 前端 `listDiscoverableGroupParticipants()` 直接依赖 `/im/v1/agents`，所以 Create group chat 面板没有真实 agent 候选，进一步阻塞真实群聊创建。

## 关键决策
1. 不新增后端 API，直接修正 runtime-selectable 筛选语义。
2. fresh runtime 场景允许“node owner 为空且 agent owner 为空”的绑定 profile 出现。
3. 已 bind 场景保持原有隔离：`node.owner_id != ''` 时，仅允许同 owner 或空 owner 的 profile 暂时出现，等待 bind reassignment 收敛。
4. 用四层证据封堵回归：
   - 集成 API：fresh runtime list 语义；
   - Gateway 集成：fresh runtime 能驱动 group conversation create；
   - real-process：真实 HTTP/WS 下 `/im/v1/agents` 非空且可建群；
   - real browser：isolated runtime 中真实面板出现候选并完成建群。

## 进度

### R1 修复 runtime selectable agent 筛选语义
- Context:
  - 刚注册但未 bind 的 canonical runtime 本该把真实 agent 暴露给 Web IM；现实现把这类 fresh runtime 当成“无 owner 不可选”，直接返回空数组。
- Decision:
  - 修改 `src/IM/infra/repositories.py` 中的 SQL：
    - 当 `COALESCE(n.owner_id, '') = ''` 时，仅返回 `ap.owner_id = ''` 的 fresh runtime profile；
    - 当 `COALESCE(n.owner_id, '') != ''` 时，返回 `ap.owner_id = ''` 或 `ap.owner_id = n.owner_id` 的 profile。
- Rationale:
  - 这样既恢复 fresh runtime agent 可见性，又继续屏蔽 stale cross-owner profile。
- Evidence:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/infra/repositories.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_agent_config_api.py`
- Status: DONE

### R2 锁定 fresh runtime → group chat 可创建链路
- Context:
  - 仅修 `/im/v1/agents` 还不够，必须证明它确实解除群聊创建主阻塞。
- Decision:
  - 改写 gateway 集成测试：
    - fresh register 后 `/im/v1/agents` 立即返回 `assistant-a` / `assistant-b`；
    - bind 后 owner 正常改写为绑定用户 owner；
    - 新增 fresh runtime 下直接创建 group conversation 的集成测试。
- Rationale:
  - 直接覆盖 M171 的主问题：群聊面板候选来源恢复后，后端群聊创建入口也必须能走通。
- Evidence:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_m103_im_gateway_e2e.py`
- Status: DONE

### R3 提供 real-process 与前端候选证据
- Context:
  - 需要说明 agent 列表来源正确，而且浏览器 Create group chat 面板能出现真实可选参与者。
- Decision:
  - 新增 real-process e2e：真实 uvicorn IM + 真实 WebSocket gateway register 后，经真实 HTTP 读取 `/im/v1/agents`，断言返回 fresh runtime agents；随后创建两个真实 agent alias user，并通过真实 HTTP 成功创建 group conversation。
  - 同时复跑前端 `im-chat-api.test.ts` 与 `chat-workspace-page.test.ts`，保留“Create group chat 面板出现真实候选并可选择创建”的 UI 门禁。
- Rationale:
  - real-process 用来证明数据源真实可用；前端回归用来证明浏览器面板仍能展示这些候选。
- Evidence:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/e2e/test_m112_real_process_roundtrip_e2e.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/frontend/src/features/chat/im-chat-api.test.ts`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
- Status: DONE

### R4 在 isolated runtime 上完成真实浏览器复验
- Context:
  - 之前的阻塞不是代码问题，而是本机外部进程抢占 `8000/18011/19011` 等端口，导致无法证明当前浏览器所连实例属于本次 M171 独占 runtime。
- Decision:
  - 先检查空闲端口，确认 `18071` 与 `19011` 可用。
  - 将 `/Users/czj/Repos/nano-multiagent/.worktrees/M171/ACCEPTANCE/M171-node-config.yaml` 的 kernel 端口改为 `18071`。
  - 用 `IM_DB_PATH=/Users/czj/Repos/nano-multiagent/.worktrees/M171/ACCEPTANCE/m171-runtime.sqlite3` 启动 isolated IM。
  - 用 Playwright 真实打开 `http://127.0.0.1:19011/bind/confirm?token=...`，点击 `Continue to chat`，进入 `Create group chat` 面板，选择两个真实 agent 并创建群聊。
- Rationale:
  - 这样能把“真实浏览器连接到正确 fresh runtime”的不确定性降到最低，拿到可信产品证据。
- Evidence:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/ACCEPTANCE/M171-node-config.yaml`
  - 浏览器脚本输出：`CHECKBOX_COUNT 2`、`CHECKBOX_LABELS ["assistant-aAgent\\n\\nRuntime agent advertised by m171-node.", "assistant-bAgent\\n\\nRuntime agent advertised by m171-node."]`
  - 真实 API 输出：
    - bind 前 `/im/v1/agents == []`，同时 `/im/v1/nodes` 显示 `agent_count=2`
    - bind 后 `/im/v1/agents` 返回 `assistant-a` 与 `assistant-b`
    - `/im/v1/conversations` 出现 `type="group"` 的 `assistant-a + assistant-b` 会话，`conversation_id=ae6710fc84f840ed98550987e3033141`
- Status: DONE

## 测试结果
- `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_agent_config_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_m103_im_gateway_e2e.py /Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/e2e/test_m112_real_process_roundtrip_e2e.py -k "agents_list_includes_fresh_runtime_profiles_before_bind or gateway_registration_materializes_runtime_agents_before_and_after_bind or fresh_runtime_agents_can_back_group_creation_before_bind or real_process_fresh_runtime_agents_list_and_group_creation_before_bind"`
  - 结果：`4 passed, 15 deselected in 0.94s`
  - 备注：存在 `websockets` / `uvicorn` 上游 deprecation warnings，不影响本次功能结论。
- `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-workspace-page.test.ts`
  - 结果：`2 passed files / 34 passed tests`
- isolated runtime 真实浏览器：
  - 结果：PASS
  - 关键输出：`CHECKBOX_COUNT 2`，并成功进入 `/chat/ae6710fc84f840ed98550987e3033141`

## 验收证据摘要
1. fresh runtime agent 列表恢复：
   - `test_agents_list_includes_fresh_runtime_profiles_before_bind()` 证明 node 未 bind 且 owner 为空时，`/im/v1/agents` 返回 `agent-fresh`，而 stale cross-owner profile 继续被过滤。
2. browser Create group chat 面板候选来源恢复：
   - `im-chat-api.test.ts` 锁定 `/im/v1/agents` → alias user → group participant option 的转换；
   - `chat-workspace-page.test.ts` 锁定点击 `Create group chat` 后可见真实候选、可选择、可触发创建。
3. fresh runtime 可成功创建群聊：
   - `test_fresh_runtime_agents_can_back_group_creation_before_bind()` 证明 gateway fresh register 后即可创建包含两个真实 agent alias 的 group conversation；
   - `test_real_process_fresh_runtime_agents_list_and_group_creation_before_bind()` 在真实 uvicorn/http/ws 入口下再次证明相同链路；
   - isolated Playwright 真实浏览器复验已经在 `/chat/ae6710fc84f840ed98550987e3033141` 成功创建群聊。
4. agent 列表来源正确：
   - real-process 与真实浏览器都证明列表来自 `node.register` materialize 的 runtime profiles，而不是静态 profile seed。

## 当前结论
- M171 主缺陷已修复：canonical fresh runtime 下 `/im/v1/agents` 不再错误返回空数组。
- `Create group chat` 面板恢复真实 agent 候选来源，fresh runtime 群聊创建不再被该问题阻塞。
- 这为 M170 / M141 的真实群聊复验清除了主要前置阻塞。

## 回滚点
- 若需要回滚，撤回以下文件即可：
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/infra/repositories.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_agent_config_api.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/e2e/test_m112_real_process_roundtrip_e2e.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/TASKS/M171-修复 canonical 运行态 agent 列表为空导致群聊无法创建.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/PROGRESS/M171-修复 canonical 运行态 agent 列表为空导致群聊无法创建.md`
