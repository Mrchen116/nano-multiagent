# refactor-489-M12: IM API 与实时测试信号收敛 — Tasks

> 对齐: ../design.md

## 目标

保留 IM HTTP/WebSocket、owner 隔离与真实服务协作的跨 seam 可观察结果，删除或改写 M11 unit/contract 重复、纯 helper 自测、静态构建产物扫描和伪 E2E。

## 退出标准

- [ ] IM auth/data HTTP、用户流与 Gateway WebSocket 的 current 公开行为仍有最低必要保护。
- [ ] IM↔Gateway↔kernel、配置 RPC、群聊/直聊与状态广播的独立连接风险仍可从跨 seam 结果观察。
- [ ] M11 已拥有的 unit/contract 逻辑不在 M12 重述；`tests/im_service/_auth_helpers.py` 保持未修改。
- [ ] M12 全范围 pytest、ruff、docs/diff/scope 门禁全绿，并记录前后 census 与处置依据。

## 测试策略

- 被测行为（来自退出标准）：JWT auth 与 owner-scoped HTTP；conversation/message/upload 的公开结果；`/im/ws/user` 鉴权、resume 与状态广播；`/im/ws/gateway` 注册、relay/receipt/report/RPC 与安全 owner 边界；IM→Gateway→kernel 的直聊、群聊、配置采用和指标结果。
- 已有测试在：`tests/im_service/integration/**` 与 `tests/im_service/e2e/**`；只收敛现有覆盖，不新建平行 test 文件。
- 落层/目录/marker：`tests/im_service/integration/`（进程内真实 FastAPI HTTP/WS 和跨模块连接，无 marker）；`tests/im_service/e2e/` 仅允许真实进程/重依赖 E2E，当前伪 E2E 删除而不补平行测试。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：pytest collect/census、重复覆盖和 private-shape inventory；无临时 test 文件。
- 用户路径分类：N/A（零产品行为变化、无前端实现）。
- UI 状态矩阵：N/A。
- 测试与验收映射：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| HTTP auth、owner 隔离和业务路由连接退化 | TestClient 真实 HTTP 请求 + 同 app 双租户 | 是 |
| user/gateway WS 鉴权、resume、relay/receipt/status 退化 | TestClient 真实 WebSocket 帧与 HTTP/WS 组合路径 | 是 |
| IM↔Gateway↔kernel 配置/聊天连接退化 | 真实 IM HTTP/WS + Gateway runtime + SDK-shaped fake kernel 边界 | 是 |
| 删除后遗漏风险 | M11 替代保护 + M12 全范围 pytest/collect/diff audit | 否（验收证据） |

- Prototype / Reference Contract：N/A。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| auth 注册/登录/refresh/logout 的公开 HTTP 结果 | `test_auth_routes.py` | keep + rewrite-merge | 保留公开 auth seam；合并等价 token 拒绝样例，不逐层重测 AuthService | R1 focused pytest |
| data routes Bearer 门禁与跨租 404 | `test_routes_require_auth.py`、`test_auth_multiuser_isolation.py` | rewrite-merge | 两文件重复 me/conversation/message/owner scope；收敛为 route 集合门禁、token 主体和同 app 多资源隔离 | R1 focused pytest |
| account bind 完整流、幂等/跨 owner 与并发原子性 | `test_account_binding_api.py`、`test_bind_atomicity.py` | keep + rewrite-merge | contract 已有字段/缺参；M12 保留 start→confirm→ownership 和竞争结果，并把 direct service 并发改为公开 HTTP seam | R1 focused pytest |
| conversation/message 基本 CRUD 与重复 auth | `test_chat_flow_integration.py`、`test_users_conversations_api.py`、`test_messages_api.py` | rewrite-merge + delete | M11 contract/repository 已拥有基本 roundtrip、rich pagination、ordering 与序列化；M12 只留 source JSONL、mark-read、boundary pagination、shadow/live、upload、offline、idempotency 等跨 seam 风险 | R1/R2 focused pytest |
| policies persistence/reseed | `test_settings_policies_api.py` | rewrite-merge | contract 已拥有字段/patch；合并为一次删除 singleton→公开 GET reseed→PATCH→GET durable roundtrip | R1 focused pytest |
| fork 404/auth route wiring | `test_fork_api.py` | delete | M11 contract 保留 unknown conversation 404，fork service 保留 auth/owner/rollback；无独立连接风险 | M11 replacement + R1 collect |
| user stream token、resume 与消息事件 | `test_user_stream_auth.py`、`test_events_sse_api.py`、`test_human_chat_sse_e2e.py`、`test_messages_api.py` 对应用例 | rewrite-merge + delete | contract 已有消息 resume；M12 只留 token/legacy identity 拒绝与有效 owner resume，删除重复 TestClient “E2E” | R2 focused pytest |
| frontend unread bundle 包含源码字符串 | `test_messages_api.py::test_frontend_runtime_bundle_exposes_mark_as_read_flow` | delete | 可选 dist 静态字符串既非 M12 seam 也常态 skip；前端行为归 M14/M16，HTTP mark-read 结果仍保留 | R2 collect + mark-read test |
| MessageResponse mapper 字段与 elapsed placeholder | `test_messages_api.py` 末尾 3 项 | delete | 直接 mapper/字段存在由 M11 message route/runtime tests 拥有；elapsed 用例最终只断言 user message `None` 字段，未验证其标题所称 agent 完成路径 | M11 focused replacement |
| agent 配置持久/合同字段、owner list 与 capabilities mapper | `test_agent_config_api.py` 对应 case | delete + keep | 删除与 M11 contract/owner repository 重复的 mock/API case；保留 real Gateway WS live config、配置采用、reregister 和 cron/skill/heartbeat RPC 的公开 HTTP 结果 | R3 focused pytest |
| agent 创建、注册/bootstrap/stale 生命周期与 channel 控制面 | `test_agent_create_flow.py`、`test_agent_user_bootstrap.py`、`test_gateway_im_registration.py`、`test_ghost_agent_reconcile.py`、`test_agent_channels_api.py` | keep + rewrite-merge | 保留 HTTP↔Gateway WS 和控制面状态；删除 mock default-workspace contract 重复并合并 stale→revive 生命周期 | R3 focused pytest |
| node board/metrics API | `test_nodes_metrics_api.py` | keep + rewrite-merge | 保留 HTTP 投影与真实 relay usage；删除由 repository 单元已完整覆盖的合成 aggregation 重述 | R3 focused pytest |
| Gateway auth/owner 安全边界 | `test_gateway_auth_boundary.py` | keep + rewrite-merge | 保留真实 WS 拒绝/关闭和 owner 不可劫持；用 user-stream/public request 结果替代 private seq/waiter 字典断言 | R4 focused pytest |
| Gateway relay/report/receipt、状态广播和 IM↔Gateway roundtrip | `test_gateway_websocket_api.py`、`test_status_broadcast_e2e.py`、`test_gateway_im_*.py`、`test_group_chat_*.py`、`test_heartbeat_config_sync_pipeline.py`、`test_event_bridge_kernel_stream.py` | keep + rewrite-merge | 这些是 HTTP/WS/Kernel 边界的独立连接保护；去掉 exact internal event choreography/call-log 冗余，保留 durable/public outcome | R4 focused pytest |
| fake kernel 自测与重复 group helper | `test_gateway_im_pipeline_integration.py`、`_gateway_helpers.py`、`_group_chat_helpers.py` | delete + rewrite-merge | helper 自身终态快照不是产品风险；两份 fake kernel 大段重复，收敛为一份被真实跨 seam case 消费的 harness | R4 focused pytest |
| init-admin CLI→HTTP 登录 | `test_init_admin_cli.py` | keep | 唯一 CLI 子进程→durable DB→公开 auth HTTP 连接保护 | R4/M12 pytest |

## Roadpoints

### R1 — Auth、租户、账户与基础 HTTP 收敛

- 状态: DONE
- 步骤: 合并 auth/data-route owner 隔离；把 bind 竞争改为 HTTP seam；收敛 policies、conversation 基本 CRUD 与 fork 重复。
- 验证: R1 changed tests + M11 对应 contract/unit 替代保护全绿。

### R2 — Message 与 user-stream 实时路径收敛

- 状态: DOING
- 步骤: 删除重复消息 mapper/basic CRUD/static dist/伪 E2E；保留 mark-read、boundary、shadow/live、upload、offline、idempotency 和 token-auth user stream。
- 验证: message/user-stream focused pytest + collect 全绿。

### R3 — Agent、Node 与配置 RPC 收敛

- 状态: TODO
- 步骤: 删除 M11 contract/repository 重复，保留 real WS live config、agent create/register/bootstrap/channel 与 public RPC 结果；合并 stale lifecycle。
- 验证: agent/node/config focused pytest 全绿。

### R4 — Gateway、群聊与共享 harness 收敛

- 状态: TODO
- 步骤: 保留 relay/receipt/report/status、安全 owner 边界和 IM↔Gateway↔kernel 结果；替换 private 状态断言；合并重复 fake kernel helper，删除 helper 自测。
- 验证: gateway/group/direct/event focused pytest 全绿。

### R5 — 全量门禁与测试 census

- 状态: TODO
- 步骤: rebase 最新 unit，运行 M12 collect/pytest、ruff、docs/diff/scope，记录前后 census、warning 与删改理由。
- 验证: 所有退出标准打勾，M12 全范围全绿且无越界修改。
