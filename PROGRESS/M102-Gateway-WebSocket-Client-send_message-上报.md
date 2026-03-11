# M102 Progress — Gateway WebSocket Client + send_message + 上报

## Baseline
- 在 `/Users/czj/Repos/nano-multiagent/.worktrees/M102` 执行 `pytest -q`
- 结果：`678 passed, 4 skipped, 246 warnings`

## 进展记录
- 已先阅读顶层 SPEC、NodeGateway-SPEC、IM-SPEC、内核设计 SPEC、LOGBOOK、ROADMAP、COMMENTING_GUIDE 后再编码。
- 发现 M100 只完成本地 channel/pipeline 骨架，M102 目标模块与产品工具尚未落地。
- 新增 Gateway 侧模块：
  - `src/personal_assistant/ws/im_connection.py`
  - `src/personal_assistant/reporter/upstream_reporter.py`
  - `src/personal_assistant/channels/web_relay_adapter.py`
  - `src/personal_assistant/config/sync_client.py`
- 产品工具已纠偏：删除误放在 `src/personal_assistant/send_message_tool_impl.py` 的实现，改为产品归属的 `src/agent/products/personal_assistant/tools/send_message.py`，并通过 `toolsets.py` 暴露到默认工具集。
- focused tests 已覆盖：
  - IM WebSocket 连接/重连/下推处理
  - register/heartbeat/report/delivery_receipt frame 生成
  - relay.message → WebRelayAdapter → InboundMessage
  - send_message 工具 contract + personal_assistant profile 默认工具集暴露

### R102.1 Gateway websocket / relay / reporting / send_message 收口
- Context:
  - Milestone 明确要求 `send_message` 必须属于 `agent.products.personal_assistant.tools/` 并经产品 toolset/defaults 暴露；现状实现误放在 `src/personal_assistant/send_message_tool_impl.py`，不满足产品边界。
  - Gateway ↔ IM 只要求 M102 交付协议边界与本地自治，不要求本 milestone 内完成完整进程编排。
- Decision:
  - 保留 `ws/im_connection.py`、`reporter/upstream_reporter.py`、`channels/web_relay_adapter.py`、`config/sync_client.py` 作为 Gateway 侧最小闭环。
  - 将 `send_message` 工具迁移到 `src/agent/products/personal_assistant/tools/send_message.py`，并把 `send_message` 加入 `src/agent/products/personal_assistant/toolsets.py` 的默认工具列表。
  - 更新测试直接 import 产品工具路径，并补 profile 断言确保默认工具集真实暴露 `send_message`。
- Rationale:
  - 这样既满足 SPEC 的产品归属边界，也利用现有 product tool loader 自动装配，不需要在 runtime/server 层加特判。
- Evidence:
  - Tests: `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M102/tests/unit/personal_assistant/test_m102_gateway_im_connection.py /Users/czj/Repos/nano-multiagent/.worktrees/M102/tests/unit/test_personal_assistant_profile.py /Users/czj/Repos/nano-multiagent/.worktrees/M102/tests/unit/test_platform_bootstrap.py` -> `28 passed in 0.19s`
  - Baseline: `pytest -q` 初始失败 1 条，原因为当前 agent worktree 缺失 `/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-ab737c91/多产品架构调整建议.md`，属于外部工作树文档环境问题，不在 M102 scope。
  - Entry: `test_im_connection_connects_registers_and_handles_downstream_frames`、`test_im_connection_retries_with_exponential_backoff_until_cap`、`test_send_message_tool_dispatches_via_gateway_boundary` 与 profile/toolset 断言均通过。
- Rollback:
  - 若需回退，回到本里程碑开始前的 `milestone/M102` 头部稳定点。
- Commits: C1=N/A（延续已有部分实现后直接收口）, C2=`f2019a8`, C3=未拆分（本次按用户要求直接提交收口）
- Next:
  - 若后续补完整进程编排，可在 M103+ 接入 bootstrap/lifecycle，并保持当前产品工具归属不回流到 gateway 包。

## 当前产品/交互风险观察
- Gateway 入口 `main.py` 仍是 M98/M100 级别 skeleton，尚未把 channel runtime、IM connection manager、scheduler 组装进统一常驻生命周期；本 milestone 会先补核心模块与测试，但完整进程编排仍存在后续整合工作。
- 当前 send_message 工具只建立产品侧契约与 dispatcher 边界；若没有 gateway dispatcher 装配，运行时仍不会真实跨节点投递。
- WebRelayAdapter 目前只承接 relay.message 规范化，不含浏览器端 delivery UX/重试提示；这类成熟产品体验还需要 M103 集成阶段继续打磨。
