# M103 IM ↔ Gateway 端到端集成

## 前置确认
- 已先阅读 `/Users/czj/.codex/skills/tdd-execution-worker/SKILL.md`、`/Users/czj/Repos/nano-multiagent/SPEC.md`、`/Users/czj/Repos/nano-multiagent/docs/NodeGateway-SPEC.md`、`/Users/czj/Repos/nano-multiagent/docs/IM-SPEC.md`、`/Users/czj/Repos/nano-multiagent/docs/内核设计SPEC.md`、`/Users/czj/Repos/nano-multiagent/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/ROADMAP.md`、`/Users/czj/Repos/nano-multiagent/COMMENTING_GUIDE.md`。
- 本 Milestone 的代码与文档将遵守 `COMMENTING_GUIDE.md` 的 public API docstring / 注释规范。
- 参考 LOGBOOK：主链路必须经过真实入口验证；优先补 IM ↔ Gateway 真实集成链路，避免只停留在 unit happy path。

## 当前处境
- Milestone: M103 / IM ↔ Gateway 端到端集成
- execution_mode: parallel
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M103`
- branch: `milestone/M103`
- 测试门禁命令: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M103/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/im_service /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/unit/personal_assistant /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/integration/test_personal_assistant_bootstrap_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/integration/test_personal_assistant_server_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M103/tests/e2e/test_personal_assistant_main_e2e.py`
- 基线结果: 待建立（最初误用了不存在的 `tests/personal_assistant` 路径，需以现有 `tests/unit/personal_assistant` 等真实目录重跑）
- allowed_scope:
  - `src/IM/**`
  - `src/personal_assistant/**`
  - `tests/im_service/**`
  - `tests/unit/personal_assistant/**`
  - `tests/integration/test_personal_assistant_*`
  - `tests/e2e/test_personal_assistant_*`
  - `TASKS/M103-*.md`
  - `PROGRESS/M103-*.md`
- forbidden_scope:
  - `data/dev-tasks.json`
  - M106 critique / product review work
  - 与 M103 无关的 CLI/内核大范围重构

## Roadpoints

### R1 Web IM ↔ Gateway ↔ kernel 消息往返与多 Agent 路由
- Status: TODO
- Acceptance:
  - 浏览器侧发消息后，IM 持久化并通过 WS 下推 `relay.message`。
  - Gateway 经 `WebRelayAdapter` + `InboundPipeline` 调用 kernel，并把回复回送到 Web IM 通道。
  - 覆盖 direct/group 会话和显式/绑定/默认 Agent 路由行为。
  - 回复与 relay/task 元数据可被测试观察，证明完整链路打通。
- Tests Plan:
  - unit: 补 gateway pipeline / relay adapter 的边界覆盖。
  - integration: 新增 IM+Gateway 组合测试，走 HTTP + websocket + pipeline 真实入口。
  - e2e: 浏览器less roundtrip 验证最小完整链路。
  - 不做 contract：现有 M97/M102 contract 已覆盖消息协议字段，M103 重点是跨边界联调。
- Expected Tests:
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py::test_web_im_message_roundtrip_browserless`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py::test_multi_agent_routing_prefers_explicit_then_binding_then_default`
- DoD:
  - 上述测试先红后绿。
  - 门禁命令全绿。
  - `PROGRESS/M103-*.md` 记录证据与回滚点。

### R2 设备绑定 + 配置同步通知端到端
- Status: TODO
- Acceptance:
  - 设备绑定 start/confirm 完整打通，节点 owner 与 node-local agents 自动归属当前用户。
  - Agent 配置更新后可向已连接 Gateway 下推 `config.sync`，Gateway 记录最新版本/触发 fetch hook。
  - 覆盖已开始会话不受 profile_version 变更影响的边界。
- Tests Plan:
  - integration: 复用 IM app websocket + HTTP patch 测试绑定与 config sync。
  - unit: 若需最小补齐 sync client / handler 行为边界。
  - 不做 e2e UI：browserless 足够覆盖此里程碑的服务协同。
- Expected Tests:
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py::test_device_binding_end_to_end_updates_node_and_agent_owner`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py::test_agent_config_sync_notifies_connected_gateway`
- DoD:
  - 绑定与 config sync 证据写入 PROGRESS。
  - 门禁命令全绿。

### R3 IM 离线自治 + 群聊 @mention 门控
- Status: TODO
- Acceptance:
  - IM websocket 不可用时，Gateway 本地外部/本地通道主路径仍可处理消息，不依赖 IM 在线。
  - 群聊未 @提及时不触发 kernel；@提及、回复 Agent、或控制命令时才放行。
  - 覆盖 group conversation policy 与 `NO_REPLY`/跳过执行语义中的至少“未命中门控不执行”。
- Tests Plan:
  - unit/integration: 给 inbound pipeline 增加 mention gate 行为覆盖，断言 kernel 未被调用。
  - integration: IM 断线仅影响 websocket 连接，不影响本地通道入站执行。
  - 不做前端真浏览器：本 milestone 关注 gateway 控制平面与路由自治。
- Expected Tests:
  - `tests/unit/personal_assistant/test_m103_gateway_im_integration.py::test_group_message_without_mention_is_ignored`
  - `tests/unit/personal_assistant/test_m103_gateway_im_integration.py::test_group_message_with_mention_or_reply_runs`
  - `tests/integration/test_personal_assistant_server_integration.py::test_gateway_local_channel_keeps_working_when_im_offline`
- DoD:
  - 先红后绿，门禁全绿，PROGRESS 记清边界。

### 收尾
- Status: TODO
- Acceptance:
  - 更新 `TASKS/M103-*.md`、`PROGRESS/M103-*.md`，补齐测试证据、回滚点、提交哈希。
  - 在 `milestone/M103` 上提交本 milestone 变更。
  - 汇报 summary / tests / commit hash，不涉及 M106 critique。
