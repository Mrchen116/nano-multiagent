# bugfix-467-M1: node.register 播种 agent skills/tool_allowlist — Tasks

> 对齐: ../fix.md

## 目标

让 Gateway 在 `node.register` 中携带每个 agent 的 `skills` / `tool_allowlist`；IM 在首次创建 agent profile 时按 first-seen-wins 把这两个字段播种进去，使 mirror 出生即真值，消除 reconcile 把空壳 v1 碾压为真值的问题。

## 退出标准

- [ ] `UpstreamReporter.send_register()` 的 payload 包含 `agent_skills` 与 `agent_tool_allowlist`（按 agent_id 映射的列表）。
- [ ] IM 侧 `node.register` 处理把上述两个种子字段透传给 `GatewayNodePersistence.register()`。
- [ ] `GatewayNodePersistence.register()` 在 profile 不存在时用种子值创建；已存在 profile 保持原值不被覆盖。
- [ ] reconcile 逻辑与 `resolve_enabled_tools`「空=零工具」语义保持不变。
- [ ] 单测覆盖：注册负载序列化、IM 建 profile 播种、已存在 profile 不被覆盖。
- [ ] live 证据：用 `scripts/e2e-up.sh` 起 ephemeral IM + Gateway，curl `GET /im/v1/agents/<id>/config?source=mirror` 与 `?source=live` 均显示非空 skills/tool_allowlist。

## 测试策略

- 被测行为：
  1. Gateway `node.register` payload 含 per-agent skills / tool_allowlist。
  2. IM 收到注册后，为全新 agent 创建 profile 时写入种子 skills / tool_allowlist。
  3. IM 对已有 profile 的 agent 重注册时，不覆盖现有 skills / tool_allowlist。
- 已有测试在：`tests/unit/personal_assistant/test_gateway_upstream_reporter.py`（扩展）、`tests/im_service/contract/test_gateway_protocol_contract.py`（可能扩展）。
- 新建测试：`tests/unit/IM/test_gateway_persistence_seed.py`（若 IM 单元测试目录不存在则按现有目录结构放置；先检查 `tests/unit/IM/` 或 `tests/im_service/` 下 persistence 测试位置）。
- 落层/目录/marker：
  - Gateway payload：tests/unit/personal_assistant/，无 marker。
  - IM seeding：tests/unit/IM/（或 tests/im_service/），无 marker。
- 可选依赖 importorskip：无。
- 一次性验收证据（收尾删除/不进套件）：e2e curl 输出截图或文本日志，落 `M1-fix/evidence/`。

## Roadpoints

### R1 — 注册播种 Red 测试

- 步骤:
  - 在 `test_gateway_upstream_reporter.py` 扩展 `send_register` 断言：payload 必须包含 `agent_skills` 与 `agent_tool_allowlist`，且值与 `AgentWorkspaceConfig` 一致。
  - 在 IM 侧写红测试：全新 DB 收到 `node.register` 后，`get_profile` 的 skills/tool_allowlist 等于注册种子；已存在 profile 时重注册不被覆盖。
- 验证: 测试先失败，失败点 = 当前缺少 agent_skills / agent_tool_allowlist 字段或播种逻辑。

### R2 — 实现注册播种

- 步骤:
  - `upstream_reporter.py`: `send_register` 增加 `agent_skills` 与 `agent_tool_allowlist` 两个字典。
  - `gateway_handler.py`: `_handle_register` 解析并透传这两个字段到 `node_persistence.register()`。
  - `gateway_persistence.py`: `register()` 新增 `agent_skills` / `agent_tool_allowlist` 参数；仅在 `existing is None` 创建 profile 时使用种子值。
- 验证: R1 测试转绿；跑相关单元测试 + contract 测试全绿。

### R3 — 回填 fix.md 与 live e2e 验证

- 步骤:
  - 回填 `fix.md`「修复」「验证」两段。
  - 用 `scripts/e2e-up.sh` 起 ephemeral IM + Gateway（确认 `~/.nano-assistant/config.yaml` 的 agents 带 skills/tool_allowlist）。
  - curl `GET /im/v1/agents/<id>/config?source=mirror` 与 `?source=live` 确认非空。
  - `scripts/e2e-down.sh` 收尾。
- 验证: fix.md 更新；live curl 输出保存到 `M1-fix/evidence/`。
