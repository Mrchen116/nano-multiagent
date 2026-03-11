# M103 IM ↔ Gateway 端到端集成

## 启动记录
- 已阅读：`/Users/czj/.codex/skills/tdd-execution-worker/SKILL.md`、`/Users/czj/Repos/nano-multiagent/SPEC.md`、`/Users/czj/Repos/nano-multiagent/docs/NodeGateway-SPEC.md`、`/Users/czj/Repos/nano-multiagent/docs/IM-SPEC.md`、`/Users/czj/Repos/nano-multiagent/docs/内核设计SPEC.md`、`/Users/czj/Repos/nano-multiagent/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/ROADMAP.md`、`/Users/czj/Repos/nano-multiagent/COMMENTING_GUIDE.md`。
- 注释规范承诺：后续新增/修改 public API 将补齐 Google 风格 docstring；注释只解释意图、边界、代价，不复述代码。
- 当前处境：M103，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M103`，branch=`milestone/M103`。
- 测试门禁：`PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M103/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/im_service /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/unit/personal_assistant /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/integration/test_personal_assistant_bootstrap_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/integration/test_personal_assistant_server_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/e2e/test_personal_assistant_main_e2e.py`
- 基线备注：首次尝试误用了不存在的 `tests/personal_assistant` 路径，未形成有效基线；后续以真实目录重建。
- prevention / 注意事项：
  - 主链路验证必须经过真实入口（HTTP / websocket / gateway pipeline），不接受只靠 isolated unit 断言“看起来打通”。
  - 仅收口 M103 集成链路、测试与 M103 文档，不做 M106 critique，不改 `data/dev-tasks.json`。
  - 优先补真实缺口；若只缺证据，则以 focused integration/e2e tests 证明现有实现满足 exit criteria。

## 实施记录
### R1 Web IM ↔ Gateway ↔ kernel 消息往返与多 Agent 路由
- Context: M97/M102 已分别覆盖 IM websocket 协议和 Gateway websocket 客户端，但缺少真正把 HTTP 发消息、WS 下推、Gateway pipeline、kernel 调用、回发统一串起来的 browserless 证据；同时旧集成测试仍把 personal_assistant 工具集视为 `{read, task}`，与 M102 的 `send_message` 现实不一致。
- Decision: 新增 `tests/im_service/integration/test_m103_im_gateway_e2e.py`，用同一测试同时驱动 IM HTTP API、gateway websocket、`WebRelayAdapter`、`InboundPipeline` 与 fake kernel；并把旧 capability/bootstrap 断言更新为包含 `send_message` 的当前产品事实。
- Rationale: M103 的核心价值是跨边界联调证据，而不是继续细拆单模块 unit；browserless 组合测试更能防止“协议都各自通过，但接线没打通”的假阳性。
- Evidence:
  - Tests: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M103/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/im_service/integration/test_m103_im_gateway_e2e.py /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/integration/test_personal_assistant_bootstrap_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/integration/test_personal_assistant_server_integration.py`
  - Entry: `test_web_im_message_roundtrip_browserless` 证明 `POST /im/v1/conversations/{id}/messages` 生成 `relay.message`，Gateway 接收后创建 kernel session、发起 run，并把回复回送到 `web_relay` 出站消息。
- Rollback: 首选回退到本 milestone 开始前的分支头（计划提交后、实现前稳定点）。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 补设备绑定/config sync 与群聊门控/离线自治证据。

### R2 设备绑定 + 配置同步通知端到端
- Context: M96 已验证绑定 API、M97 已验证 `config.sync` 推送，但缺少把“节点/Agent owner 变更”与“配置更新后通知已连接 Gateway”放在同一 milestone 下的集成证据。
- Decision: 在新的 M103 集成测试中补 `test_device_binding_end_to_end_updates_node_and_agent_owner` 与 `test_agent_config_sync_notifies_connected_gateway`，直接断言绑定后 `owned_node_ids` 与 node-local `agent_profiles.owner_id` 同步，以及 profile patch 后 `config.sync` frame 被连接中的 Gateway 消费。
- Rationale: 这些路径主要缺的是联调证据而不是业务实现；通过 focused integration tests 可以把 M96/M97/M99 既有能力串成 M103 可验收故事线。
- Evidence:
  - Tests: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M103/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - Entry: 绑定测试覆盖 `POST /im/v1/bind(start)` → `POST /im/v1/bind(confirm)` → `GET /im/v1/me` / `GET /im/v1/agents/{id}/config`；config sync 测试覆盖 `PATCH /im/v1/agents/{id}/config` 后由 `GatewayHandler.push_config_sync()` 下推给在线节点。
- Rollback: 首选回退到完成 R1 后的稳定点。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 补群聊 @mention gate 与 IM 离线本地自治验证。

### R3 IM 离线自治 + 群聊 @mention 门控
- Context: NodeGateway-SPEC 要求群聊未 @提及时不触发 Agent，且 IM 离线不影响外部 IM 主路径；现有 `InboundPipeline` 会直接处理所有群聊消息，没有门控，离线自治也缺 focused regression tests。
- Decision: 在 `src/personal_assistant/gateway/inbound_pipeline.py` 增加 `_should_process()`，用 `mentioned_agent_ids`、`reply_to_agent_id`、`trigger`、文本 `@agent_id` 作为放行条件；未命中时直接返回 `None`，避免创建 kernel session。新增 `tests/unit/personal_assistant/test_m103_gateway_im_integration.py` 覆盖未提及忽略、提及/回复放行、本地通道在无 IM websocket 时仍可执行；同步把旧 `test_gateway_pipeline.py` 群聊绑定样例改成显式 mention，避免被新门控误拦截。
- Rationale: 把 gate 放在 Gateway 路由边界最省成本，也最符合规范——未命中的群聊噪音不应占用 kernel queue / session；同时不会影响 direct chat 与本地自治路径。
- Evidence:
  - Tests: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M103/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/unit/personal_assistant/test_m103_gateway_im_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/unit/personal_assistant/test_gateway_pipeline.py`
  - Entry: `test_group_message_without_mention_is_ignored` 断言 kernel 完全未被调用；`test_local_channel_keeps_working_without_im_connection` 断言仅靠本地 channel + pipeline 也能完成消息执行与回发。
- Rollback: 首选回退到完成 R2 后的稳定点。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 收口全文档、记录门禁结果并提交。

## 验证
- Focused red/green 子集：`PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M103/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/im_service/integration/test_m103_im_gateway_e2e.py /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/unit/personal_assistant/test_m103_gateway_im_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/integration/test_personal_assistant_bootstrap_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/integration/test_personal_assistant_server_integration.py` → `22 passed`
- 收口门禁：`PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M103/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/im_service /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/unit/personal_assistant /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/integration/test_personal_assistant_bootstrap_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/integration/test_personal_assistant_server_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/e2e/test_personal_assistant_main_e2e.py` → `102 passed`

## 进行中
- 待补：提交哈希回填到 `Commits` 字段，并在 milestone/M103 上创建 git commit。

## 结果摘要
- 已完成 M103 范围内的 browserless IM↔Gateway↔kernel roundtrip、设备绑定端到端、config sync 通知、IM 离线本地自治、多 Agent 路由证据与群聊 @mention gate。
- 未触碰 M106 critique，也未修改 `data/dev-tasks.json`。

## 相关文件
- `/Users/czj/Repos/nano-multiagent/.worktrees/M103/src/personal_assistant/gateway/inbound_pipeline.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/im_service/integration/test_m103_im_gateway_e2e.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/unit/personal_assistant/test_m103_gateway_im_integration.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/unit/personal_assistant/test_gateway_pipeline.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/integration/test_personal_assistant_bootstrap_integration.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/integration/test_personal_assistant_server_integration.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M103/TASKS/M103-IM-Gateway-端到端集成.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M103/PROGRESS/M103-IM-Gateway-端到端集成.md`
