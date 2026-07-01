# feat-447-M7: external-channel-full-sync — Tasks

> 对齐: ../design.md M7 / Runbook for Reviewer

## 目标

外部 channel（本 milestone 以飞书为首个实现）在内部 IM 中形成可见的独立影子会话：飞书用户消息与 agent 回复完整同步到 IM，IM 影子会话入口复用同一个 kernel session 但不回写飞书，外部群聊未 @ 背景可跨入口进入上下文。

## 退出标准

- [ ] IM 持久化支持 `conversations.external_source` / `external_chat_id` 与 `messages.sender_display_name`，旧库自动迁移。
- [ ] `POST /im/v1/conversations/external/find-or-create` 以 `(external_source, external_chat_id, config_agent_id, owner_id)` 幂等创建/更新影子会话，复用 `config_agent_id`，不新增第二套 agent id。
- [ ] Relay payload 对影子会话回环 `external_source` / `external_chat_id` / `agent_id` / `trigger_source` / `conversation_type`。
- [ ] Gateway 使用外部身份生成 session key 和 group buffer key，`web_relay` 的 IM conversation id 只作为 delivery/shadow id。
- [ ] Feishu 未 @ 群消息走 `sync_only` 入站：同步到 IM、写 GroupContextStore，但不分配 session、不提交 run、不重复 adapter 本地 buffer。
- [ ] 外部 channel 用户消息 best-effort 同步到 IM；同步失败不阻塞飞书回复，也不触发 IM lazy direct 创建。
- [ ] run context 经 lifecycle accepted seed `shadow_conversation_id`；外部 run 的 agent 回复落到 IM 影子会话，shadow 不可用时跳过 IM 同步。
- [ ] IM 影子 group 入口在 mention gate 前等效 @agent；IM 触发的 run 只写 IM，不回写飞书。
- [ ] `ownerOpenId` 配置校验生效，owner 从飞书发的消息在 IM 显示为「你」。
- [ ] 非 e2e 测试无回归；live-critical 验收使用 `lark-cli im +messages-send --as user` 向 `<WT_CFG>` 中同 `appId` 的 Bot 发送 nonce，证明确实经真实飞书入站跑到用户可见结果。

## 测试策略

- 被测行为（来自退出标准）：IM schema/API/sender display name；RelayService metadata 回环；WebRelayAdapter 外部身份映射；session key / group buffer key 外部身份优先；sync_only 短路与 buffer；run context shadow seed / no lazy direct；per-run reply_context 路由；Feishu ownerOpenId 与未 @ 入站；真实 lark-cli 用户入站。
- 已有测试在：扩展 `tests/im_service/unit/test_db_init.py`、`tests/im_service/unit/test_repositories_user_conversation.py`、`tests/im_service/unit/test_repositories_message.py`、`tests/im_service/unit/test_relay_service_payload.py`、`tests/im_service/integration/test_messages_api.py`、`tests/unit/personal_assistant/test_gateway_web_relay_adapter.py`、`tests/unit/personal_assistant/test_inbound_pipeline_session.py`、`tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`、`tests/unit/test_feishu_adapter.py`、`tests/unit/test_feishu_config.py`；必要时新建单一行为文件，理由：若现有文件无对应最低层行为落点。
- 落层/目录/marker：unit/integration 为主，marker 无；真实飞书验收作为一次性 live 证据记录到 progress，不提交到 pytest 套件。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：worktree IM/Gateway 日志、`lark-cli` 命令输出、IM shadow conversation/message id、飞书回复 message id 或时间戳。

## Roadpoints

### R1 — IM 影子会话与消息持久化

- 状态: DONE
- 步骤: 增加 IM schema migration、domain/repository 字段、`external/find-or-create` 服务/API、sender_display_name 写入与响应。
- 验证: DB migration/repository/API/message route 单测或集成测试红转绿。

### R2 — IM relay metadata 回环到 Gateway

- 状态: TODO
- 步骤: RelayService 从 conversation 外部字段与 config agent 生成 metadata，WebRelayAdapter 保留 IM conversation id 作为 delivery id，并把外部身份、trigger_source、conversation_type、group mention 标记传给 InboundMessage。
- 验证: RelayService payload 与 WebRelayAdapter 单测红转绿。

### R3 — Gateway 外部 session identity、sync_only 与 group buffer

- 状态: TODO
- 步骤: session key / group buffer key 外部身份优先；FeishuAdapter 去掉本地未 @ buffer，改走 sync_only；Pipeline sync_only 只同步+buffer+短路；ownerOpenId / sender_display_name / chat title metadata 接入。
- 验证: session key、Feishu adapter、Pipeline sync_only/group buffer/config 单测红转绿。

### R4 — Shadow conversation 同步、run context 与出站路由

- 状态: TODO
- 步骤: Gateway 在外部入站早期 best-effort find-or-create + 写用户消息；accepted lifecycle seed shadow conversation id；外部 shadow 失败时不 lazy direct；IM shadow group gate 前触发；IM 触发 run 不回写飞书。
- 验证: InboundPipeline lifecycle/outbound/router/main wiring 单测红转绿，相关窄测试通过。

### R5 — 非 e2e 门禁与真实飞书端到端验收

- 状态: TODO
- 步骤: 跑窄测与 `pytest -m "not e2e"`；启动 worktree IM/Gateway；用 runbook 中 appId 校验后的 `lark-cli im +messages-send --as user` 发 nonce 到目标 Bot，核对飞书回复、IM 影子会话和消息。
- 验证: progress.md 记录真实入口证据、日志路径、message/conversation id 与环境 caveat。
