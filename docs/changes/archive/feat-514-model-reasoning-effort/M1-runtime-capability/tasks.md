# feat-514-M1 tasks — model-reasoning-effort

> 单一垂直切片：运行时、Gateway、IM 和 Web IM 一起交付，避免出现只可配置而不可实际生效的半成品。

## Roadpoints

- [x] R1: YAML `reasoning` capability 解析、序列化与安全的节点 capability 投影。
- [x] R2: Agent profile 的 `reasoning_effort` 在 SDK/runtime/session identity 与两种 provider request body 中生效。
- [x] R3: IM 与 Gateway 使用同一 canonical operation fingerprint，实现 create/apply 的持久回执、重试和恢复。
- [x] R4: Web IM create/detail 表单按 model 呈现 selectable、fixed 和未声明 capability 三种状态。
- [x] R5: 隔离 IM + Gateway + 浏览器验收，覆盖三态和保存后回读。

## 测试策略

- 配置、runtime 与 provider packet：
  `tests/unit/personal_assistant/config/test_parse_llm.py`、
  `tests/unit/test_llm_reasoning_request_body.py`、
  `tests/contract/test_llm_interfaces_contract.py`。
- Gateway operation 和 IM/Gateway 协议：
  `tests/unit/personal_assistant/test_gateway_config_operations.py`、
  `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py`、
  `tests/im_service/contract/test_agent_config_contract.py`、
  `tests/im_service/contract/test_agent_create_contract.py`、
  `tests/im_service/integration/test_agent_config_operation_flow.py`、
  `tests/im_service/unit/test_agent_config_operations.py`。
- Web IM state transitions：
  `src/IM/frontend/src/features/settings/agents/model-reasoning-field.test.tsx`，
  并扩展 create/edit/API/WS consumer tests，覆盖 model switch、fixed、未声明、stale 和 pending operation。
- 一次性真实验收：仓库 `config/e2e/gateway.yaml` 提供 selectable/fixed/未声明三态；真实浏览器创建
  `reasoning-e2e` Agent，选择 DeepSeek `high` 后回读同一选择。运行产物不提交。

## 边界说明

- Provider request body 的静态 `extra_request_body` 属于模型协议配置；用户只保存 `reasoning_effort`，不在 YAML 重复写请求字段映射。
- `reasoning: fixed` 是模型固定行为的展示能力，不写入 Agent 的 `reasoning_effort`。
