# feat-447-M8: fix-live-startup — Tasks

> 对齐: ../acceptance.md Round 4 / ../verification.md Round 4 / ../design.md Runbook for Reviewer

## 目标

修复 Round 4 验收和 verifier warning 暴露的 live startup 阻塞：旧 IM DB 可自动迁移并启动，缺 `ownerOpenId` 的 runbook config 不再让 Gateway hard fail，Feishu group shadow 会话标题能使用真实群名。

## 退出标准

- [x] 旧 IM SQLite DB 缺 `conversations.external_source` / `external_chat_id` 时，`initialize_schema()` 自动增列并创建 external identity index，不再启动崩溃。
- [x] `.gateway-config.yaml` 的 Feishu channel 缺 `ownerOpenId` 时 Gateway 可启动；Gateway 自启动在 `appId` 匹配时自动写回 worktree-local `ownerOpenId`，owner 消息显示为「你」的验收路径在 runbook 中明确。
- [x] Feishu group 入站 metadata 携带 `chat_name` 或 `conversation_title`，shadow title 使用真实群名而非固定「群聊」；chat name API 未 start / 失败时不阻断入站。
- [x] 非 e2e 测试无回归；用 runbook 真栈路径启动 IM + Gateway，并用 `lark-cli im +messages-send --as user` 完成真实飞书 smoke，IM shadow conversation/message 可见。

## 测试策略

- 被测行为（来自退出标准）：legacy IM DB schema migration；Feishu config 缺 `ownerOpenId` 不阻塞 parse/registry；Feishu group chat name REST 读取和 inbound metadata 传递；shadow title 使用 `conversation_title`。
- 已有测试在：扩展 `tests/im_service/unit/test_db_init.py`、`tests/unit/test_feishu_config.py`、`tests/unit/test_feishu_integration.py`、`tests/unit/test_feishu_client.py`、`tests/unit/test_feishu_adapter.py`、`tests/unit/personal_assistant/test_inbound_pipeline_session.py`。
- 落层/目录/marker：`tests/unit/` 与 `tests/im_service/unit/`，marker 无；真实飞书 smoke 是一次性 live 证据，不进 pytest。
- 可选依赖 importorskip：沿用现有 `lark_oapi = pytest.importorskip("lark_oapi")`。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：worktree IM/Gateway logs、`lark-cli` nonce/message id、IM shadow DB query evidence。

## Roadpoints

### R1 — Round 4 live startup fixes

- 状态: DONE
- 步骤: 补 Round 4 复现测试；修复 IM legacy migration 顺序、Feishu `ownerOpenId` 非阻塞配置、group chat name REST/metadata；更新 design runbook 与 M8 progress。
- 验证: 红测失败点与反馈一致；相关窄测、`pytest -m "not e2e"`、runbook 真栈 + `lark-cli im +messages-send --as user` smoke 通过，最终 live nonce `feat447-m8-live3-20260702113138` 在 IM shadow DB 中有 conversation/message row。
