# bugfix-518-M1: Gateway-owned distill prompt — Tasks

> 对齐: [design.md](design.md) v5.3

## 实施清单

- [x] 移除 IM `source_jsonl_path` 和本机 JSONL scanner，改为 `source_node_id` projection。
- [x] 增加 owner-scoped IM distill-prompt endpoint：保留 frontend distiller/`skill_view` preflight，校验
  source/executor 同 node、idle 与 owner 后，以 request_id 请求该 Gateway。
- [x] Gateway 增加 correlated `node.distill.prompt.request/result` handler：从 durable binding 解析本机 JSONL
  path（保留 external shadow binding fallback），并复核 distiller/`skill_view`，按现有 `buildDistillDraft` 格式返回 prompt/error。
- [x] sidebar 以 node 限制多选；dialog 成功取回 prompt 后，IM 在同一 operation 创建固定 `target_node_id` 的
  direct conversation；composer 原样预填该 prompt，普通 relay 的 server pin 优先于 request `target_node_id` hint。
- [x] 删除为 IM directory scan、metadata relay、internal input injection 设计的代码/测试；builtin skill 和普通
  message relay 不改。
- [x] 记录双 Gateway browser acceptance 至 `M1-gateway-owned-distill/progress.md`。

## 测试策略

- 改写 existing conversation API/repository tests：保护 `source_agent_id + source_node_id`，不再维护 path scanner
  的内部实现断言。
- 在现有 Gateway control/API seam 增加一次 correlated prompt request/result 和离线/跨 node/source/capability/
  wrong-node failure；在 `tests/im_service/unit/test_gateway_handler.py` 和
  `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py` 验证 control request/result，在
  `tests/im_service/integration/test_messages_api.py` 验证 prompt conversation 的 server pin 压过 rebind 后 profile
  和 caller B node hint。不新增另一条 relay 或 browser E2E 测试。
- 在现有 frontend distill journey 保留“slash command + returned paths 预填、普通发送”的断言，新增同 Gateway
  锁定与 prompt endpoint error 不创建 conversation。
- 新增一个 semantic `test_gateway_distill_prompt_resolver.py`，只保护 binding→本机 path→prompt 这个新 owner
  seam 的成功与 all-or-nothing source/capability failure。
- 运行相关 pytest/Vitest、frontend build、ruff、`git diff --check`、docs check；双 Gateway 真栈只作为一次性
  browser acceptance evidence，结束后清理进程。

### 受影响测试处置

| 现有测试 | 处置 | 最终保护 |
|---|---|---|
| `tests/im_service/integration/test_users_conversations_api.py` | rewrite-merge | `source_agent_id + source_node_id` public projection，不再暴露 scanner path。 |
| `tests/im_service/unit/test_repositories_user_conversation.py` | rewrite-merge / delete nested scanner case | 保留 owner/run-state；删除 IM recursive path/nested scan implementation assertions。 |
| `src/IM/frontend/src/features/chat/chat-workspace.integration.test.tsx` | rewrite-merge | returned current-format prompt、readiness 和普通发送。 |
| `src/IM/frontend/src/features/chat/components/conversation-sidebar.test.tsx` | rewrite-merge | source-node same-Gateway selection。 |
| `tests/im_service/unit/test_gateway_handler.py` | rewrite-merge | correlated prompt control request/result。 |
| `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py` | rewrite-merge | Gateway control request handler/result。 |
| `tests/im_service/integration/test_messages_api.py` | rewrite-merge | pinned direct conversation ignores legacy client node hint。 |
