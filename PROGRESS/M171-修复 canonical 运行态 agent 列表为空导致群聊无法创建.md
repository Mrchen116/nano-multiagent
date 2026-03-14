# M171 Progress — 修复 canonical 运行态 agent 列表为空导致群聊无法创建

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M171`
- 已确认 branch：`milestone/M171`
- 已确认约束：仅在该 worktree 实施修复；不修改 `data/dev-tasks.json`
- 已阅读：
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M141/ACCEPTANCE/M141-acceptance.md`
  - `/Users/czj/Repos/nano-multiagent/docs/需求.md`
  - `src/IM/api/routes/agents.py`
  - `src/IM/application/config_service.py`
  - `src/IM/infra/repositories.py`
  - `src/IM/ws/gateway_handler.py`
  - `src/IM/frontend/src/features/chat/im-chat-api.ts`
  - `tests/im_service/integration/test_agent_config_api.py`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py`

## 最终根因结论
### 1. `/im/v1/agents` 之前混用了“配置表存在”与“运行态可选”两种口径
- 旧实现直接返回 `ConfigService.list_profiles()`，底层是 `agent_profiles` 全量配置行。
- 这只能说明“数据库里存在 profile”，并不说明“当前 canonical runtime 中该 agent 真的可选、可被群聊创建使用”。

### 2. 浏览器 Create group chat 面板的真实参与者来源是一个派生链路
- `src/IM/frontend/src/features/chat/im-chat-api.ts` 中，群聊参与者由 `listDiscoverableGroupParticipants()` 生成：
  1. 先取 `/im/v1/agents`
  2. 再确保每个 agent 对应 alias user（`agent:<agent_id>`）存在
  3. 最后从 `/im/v1/users` 推导出真正显示在 Create group chat 面板中的 participant options
- 因此，只要 `/im/v1/agents` 的口径不代表“当前 runtime 真可选 agent”，浏览器参与者列表就会漂移，最终可能为空或不可用。

### 3. 仅仅收紧 `/im/v1/agents` 查询还不够
- 在本轮真实 fresh runtime 排查中，又定位到第二层缺口：
  - Gateway `node.register` 只上报 node 在线与 `agents[]`
  - 但 IM 侧没有把这些运行态 agent ids materialize 成最小 `agent_profiles` 行
- 结果是：即使 node 在线、后续 bind 完成，`/im/v1/agents` 也可能仍然为空，因为根本没有 profile 行可选。
- 这也是 M171 的最终闭环根因：
  - 旧 `/im/v1/agents` 口径错误
  - 同时 fresh gateway 注册缺少 runtime profile materialization

## 修复决策
### R1 收紧 `/im/v1/agents` 为 runtime-selectable agents
- Decision:
  - 在 `AgentProfileRepository` 增加 `list_runtime_selectable_profiles()`。
  - 通过 `agent_profiles ap JOIN nodes n ON n.node_id = ap.node_id` 收紧返回集合。
  - 最终只返回：
    - 已绑定到 node 的 profile
    - 且 node owner 已非空
    - 且 `ap.owner_id = ''` 或 `ap.owner_id = n.owner_id`
- Rationale:
  - 防止未绑定节点在 fresh runtime 中过早暴露 agent。
  - 防止 cross-owner / stale profiles 混入运行态可选列表。
- Evidence:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/infra/repositories.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/application/config_service.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/api/routes/agents.py`
- Status: DONE

### R2 在 Gateway 注册时 materialize runtime agent profiles
- Decision:
  - 在 `GatewayHandler._handle_register()` 中，node 成功注册后：
    - 读取 websocket payload 中的 `agents[]`
    - 为每个 agent id 在 `agent_profiles` 中 upsert 最小 profile
    - 绑定 `node_id`
    - 若已有 profile，则保留已有 display/description/system_prompt 等字段
- Rationale:
  - fresh runtime 不能依赖“事先人工创建 profile”；Gateway 广告出来的运行态 agent 必须自动落到 IM 可发现层。
  - 这样 bind 完成后，`reassign_owner_by_node()` 才有真实 profile 行可改 owner，`/im/v1/agents` 才能变成真实 selectable 列表。
- Evidence:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/ws/gateway_handler.py`
- Status: DONE

### R3 补后端回归，锁定 selectable / unbound / cross-owner / fresh-register 边界
- Decision:
  - 更新 `test_agents_list_get_patch_and_conflict`，使 seed agent 绑定 node 后再验证 `/im/v1/agents`。
  - 新增 `test_agents_list_hides_unbound_and_cross_owner_profiles`。
  - 新增 `test_gateway_registration_materializes_runtime_agents_after_bind`，锁定：
    - fresh gateway 注册后、未 bind 前 `/im/v1/agents == []`
    - bind 完成后 `/im/v1/agents` 返回真实 runtime agents
- Rationale:
  - 把 M171 的两个根因都固化进回归门禁，防止再次退化为：
    - “全量 profile 列表”
    - “gateway 只注册 node 不注册 runtime agents”
- Evidence:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_agent_config_api.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_m103_im_gateway_e2e.py`
- Status: DONE

### R4 补前端回归，锁定 group participants 派生链路
- Decision:
  - 在 `src/IM/frontend/src/features/chat/im-chat-api.test.ts` 增加 `listDiscoverableGroupParticipants()` 回归测试。
  - 通过受控 `fetch` mock，覆盖：
    - runtime `/im/v1/agents` 返回两个真实 agent
    - bootstrap 自动创建 alias user
    - group participants 最终显示两个 agent 参与者
- Rationale:
  - 防止前端再次出现“agent API 有数据，但 group picker 无参与者”。
- Evidence:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/frontend/src/features/chat/im-chat-api.test.ts`
- Status: DONE

## Fresh runtime 证据
### 隔离 fresh runtime API 证据
在隔离 IM + Gateway 实例上，观察到以下过程：
1. fresh startup 后：
   - `GET /im/v1/nodes` 返回在线 node，`agent_count=2`
   - `GET /im/v1/agents` 返回 `[]`
   - 说明未绑定前不会过早暴露 agent
2. 完成 bind 后，M171 新增回归 `test_gateway_registration_materializes_runtime_agents_after_bind` 已证明：
   - `/im/v1/agents` 返回 `assistant-a` 与 `assistant-b`
   - 两者都带 `bound_nodes=["node-1"]`
   - 两者 owner 都被 reassign 到当前绑定用户

这正是 M171 所需的新来源说明：
- agent list 现在来自“Gateway 注册 materialize 的 runtime profiles” + “绑定后 owner 一致的 runtime-selectable filter”
- 之前为空，是因为 runtime 中没有被 materialize 的 profile 行，即使 node 在线也无 agent 可列出

## 测试结果
### 已执行并通过
1. `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/frontend install`
   - 结果：PASS
2. `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts`
   - 结果：PASS
   - 汇总：`1 passed, 13 tests passed`
3. `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_agent_config_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_m103_im_gateway_e2e.py`
   - 结果：PASS
   - 汇总：`8 passed in 0.53s`

## 浏览器/真实运行态验证状态
### 已完成的真实运行态验证
- 已在隔离 runtime 上确认 fresh startup 时 `/im/v1/agents` 为 `[]`、`/im/v1/nodes` 显示在线 node with `agent_count=2`，从而复现并定位“agent profile 未 materialize”的真实缺口。
- 已基于修复后的 fresh runtime 行为补齐回归，证明 bind 完成后 `/im/v1/agents` 返回真实 selectable agents。

### 本机真实浏览器复验阻塞
- 尝试在 localhost 上启动独占的 IM 实例做最终 headed browser 复验时，`8011`、`18011`、`19011` 都先后被外部已存在 IM 进程占用或争抢。
- 这导致本机浏览器若继续连接这些端口，将命中非本次 M171 独占 fresh runtime，证据不可信，因此没有伪造“浏览器已通过”。
- 额外观察到：被外部进程占用的 `19011` 实例上，`POST /im/v1/bind` 返回 `500 Internal Server Error`，进一步说明该端口上的服务不是一轮可控的 fresh M171 runtime。

## 修改文件
- `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/infra/repositories.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/application/config_service.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/api/routes/agents.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/ws/gateway_handler.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_agent_config_api.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_m103_im_gateway_e2e.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/frontend/src/features/chat/im-chat-api.test.ts`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/frontend/package-lock.json`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M171/ACCEPTANCE/M171-node-config.yaml`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M171/TASKS/M171-修复 canonical 运行态 agent 列表为空导致群聊无法创建.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M171/PROGRESS/M171-修复 canonical 运行态 agent 列表为空导致群聊无法创建.md`

## Merge readiness
- 当前状态：NOT READY
- 原因：本机存在外部 IM 进程争抢 localhost 端口，未拿到一轮完全独占的真实浏览器复验，因此不能诚实宣称“Create group chat 面板已在真实浏览器完成最终复验并成功创建群聊”。
- 代码与自动化门禁角度：READY
- 产品最终验收角度：等待在独占 localhost runtime 或干净机器上补跑一次 headed browser 复验后即可转为 merge ready。
