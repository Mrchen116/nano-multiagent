# refactor-372-M5: pa-im — Tasks

> 对齐: ../design.md v1 (Changelog 2026-05-20)

## 目标

`pytest tests/unit/personal_assistant tests/unit/IM tests/im_service -m "not e2e"` 退出 0。

完成后：
- 28 个漂移失败全部修复
- 7 个巨型文件按行为聚类拆分（拆前后用例数一致）
- 流水号文件 test_m102 / test_m103 / test_m136 重命名
- 无 >400 行文件（或列明豁免）
- SOCKS 代理环境变量在 conftest 清除

## 退出标准

- [ ] `pytest tests/unit/personal_assistant tests/unit/IM tests/im_service -m "not e2e"` 退出 0
- [ ] 修漂移：`_FakeKernelClient.send_message_async` → `submit_message`（5 失败）
- [ ] 修漂移：`sender["id"]` → `sender["user_id"]`（6 失败）
- [ ] 修漂移：IM conversations/messages 测试补 JWT auth（6 失败）
- [ ] 修漂移：ws token usage 字段（`input`/`output` → `total` 字段）（1 失败）
- [ ] 修漂移：工具集断言改 subset（2 失败，test_agent_config_api）
- [ ] 修漂移：integration 综合漂移（8 失败：chat_flow / m136 / messages_api / users_conversations）
- [ ] SOCKS 代理 env 在 personal_assistant 子树 conftest 清除（1 失败）
- [ ] 去流水号：test_m102 → test_gateway_im_connection；test_m103 → test_gateway_im_pipeline_integration；test_m136 → test_group_chat_flow
- [ ] 拆 test_main(2120) / test_gateway_pipeline(1676) / test_m103(1419) / test_m102(866) / test_repositories(790) / test_m136(697) / test_relay_service(627) 按行为，拆前后用例数一致
- [ ] 该子树无 >400 行文件（或报告列明豁免）

## 测试策略

- 被测行为（来自退出标准）：这是测试健康化 unit，本 milestone 本身不新增功能，只是修复/对齐/重构现有测试
- 已有测试在：`tests/unit/personal_assistant/`、`tests/unit/IM/`、`tests/im_service/`（修改）
- 落层/目录/marker：同现有层，无需新增 marker
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据：无（全是常驻回归）

UI 状态矩阵：N/A（纯后端测试健康化）

## Roadpoints

### R1 — 漂移修复：submit_message + sender["user_id"] + ws token_usage

修复三个纯字段/方法名漂移，不涉及流程变化：
- `_FakeKernelClient.send_message_async` → `submit_message`（test_m103_im_gateway_e2e.py 和 test_m136_group_chat_flow.py 中的 _FakeKernelClient）
- `sender["id"]` → `sender["user_id"]`、`p["id"]` → `p["user_id"]`（test_relay_service.py 6处）
- ws token_usage 字段：`{"input": X, "output": Y}` → `{"total": N}` 或对齐现码（test_ws_event_types.py 1处）

步骤：
1. 读 src/personal_assistant/gateway/inbound_pipeline.py 确认 submit_message 签名
2. 修 test_m103 和 test_m136 中 _FakeKernelClient
3. 修 test_relay_service.py 中 sender["id"] 引用
4. 读现码 ws_event_types 相关 src 确认 token_usage 结构，修 test_ws_event_types.py

验证：`pytest tests/im_service/unit tests/im_service/integration/test_m103_im_gateway_e2e.py tests/im_service/integration/test_m136_group_chat_flow.py -m "not e2e" -q`

### R2 — 漂移修复：IM conversations/messages 补 JWT auth

`test_conversation_rename.py` 和 `test_messages_broadcast.py` 未传 Authorization header，导致 401。

步骤：
1. 在两个文件中增加 helper：先注册/登录获取 access_token，之后所有 client 调用带 `Authorization: Bearer <token>`
2. test_conversation_rename.py 中 HTTP 路由测试（3个用例）补 auth
3. test_messages_broadcast.py 中 HTTP 路由测试（3个用例）补 auth

验证：`pytest tests/unit/IM/ -m "not e2e" -q`

### R3 — 漂移修复：工具集断言改 subset + integration 综合漂移

- test_agent_config_api.py：断言里对 agent 列表字段用 exact match，产品新增了 `node_status` 字段 → 改用 subset 断言（只断言关键字段）
- test_chat_flow_integration.py：unread_count 断言（assert 1 == 2）→ 对齐现码逻辑
- test_messages_api.py：unread_count 两处断言 → 对齐
- test_users_conversations_api.py：unread_count 断言 → 对齐
- test_agent_create_flow.py：字段 exact match → subset

步骤：
1. 读现码 unread_count 逻辑，确认正确期望值
2. 修各文件断言

验证：`pytest tests/im_service/integration/test_agent_config_api.py tests/im_service/integration/test_chat_flow_integration.py tests/im_service/integration/test_messages_api.py tests/im_service/integration/test_users_conversations_api.py tests/im_service/integration/test_agent_create_flow.py -m "not e2e" -q`

### R4 — SOCKS 代理 env 清除 + conftest

test_kernel_api_client.py 因 SOCKS 代理 env 失败：
- 在 tests/unit/personal_assistant/ 增加 conftest.py，autouse fixture 清除 HTTPS_PROXY / ALL_PROXY / HTTP_PROXY 环境变量

步骤：
1. 新建/更新 tests/unit/personal_assistant/conftest.py
2. 添加 autouse fixture 用 monkeypatch 清除代理 env

验证：`pytest tests/unit/personal_assistant/test_kernel_api_client.py -m "not e2e" -q`

### R5 — 全量绿基线确认

跑完整子树确认 0 failed：
`pytest tests/unit/personal_assistant tests/unit/IM tests/im_service -m "not e2e" -q`

### R6 — 拆巨型文件：test_relay_service(627) + test_repositories(790)

按行为聚类拆分（不改用例逻辑，只重新分组）：
- test_relay_service.py(627) → test_relay_service_enqueue.py + test_relay_service_broadcast.py
- test_repositories.py(790) → test_repositories_user.py + test_repositories_conversation.py + test_repositories_message.py（按实体分）

拆前后用例数一致验证。

### R7 — 重命名流水号 + 拆 test_m103(1419) + test_m136(697)

- test_m103_im_gateway_e2e.py → test_gateway_im_pipeline_integration.py（重命名）
- test_m136_group_chat_flow.py → test_group_chat_flow.py（重命名）
- 视 test_m103 行为聚类可拆：direct_chat / group_chat / config_sync 三组各一文件（共保持用例数）
- test_m136(697) 拆为 test_group_chat_flow_creation.py + test_group_chat_flow_events.py

### R8 — 拆巨型文件：test_m102(866) → test_gateway_im_connection.py 及子文件

- test_m102_gateway_im_connection.py → test_gateway_im_connection_setup.py + test_gateway_im_connection_lifecycle.py
- 重命名消除流水号

### R9 — 拆巨型文件：test_main(2120) + test_gateway_pipeline(1676)

最大两个文件：
- test_main.py(2120) 按 Gateway 启动/停止/配置/心跳/渠道/命令 聚类拆分
- test_gateway_pipeline.py(1676) 按 pipeline 阶段（inbound/auth/dispatch/error）聚类拆分

每次拆前先统计用例数，拆后再次统计确认一致。

### R10 — 最终验收 + 豁免报告

- 跑 `pytest tests/unit/personal_assistant tests/unit/IM tests/im_service -m "not e2e" -q` 确认全绿
- 列出所有 >400 行文件检查（如果有豁免说明原因）
- 确认所有流水号文件已消除
