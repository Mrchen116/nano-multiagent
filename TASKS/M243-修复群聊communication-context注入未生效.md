# M243 — 修复群聊 communication context 注入未生效

## 目标

修复 group chat 生产链路中 communication context / system prompt 未生效的问题：
- personal_assistant 产品 hook 必须按真实模块 stem 正常加载
- IM relay metadata 必须携带真实 `participant_agent_ids`
- Gateway 创建 session 时必须把真实参与者传给 kernel
- before_agent_start 必须把 communication context 追加到真实 system prompt，而不是覆盖掉它
- 通过真实请求日志验证最终 system prompt 中出现 `[Communication Context]`、`your_agent_id`、`group_participants`

## Roadpoints

### R1 — 修复 hook 加载与群聊 metadata 透传回归

**Acceptance**：
1. `personal_assistant` 默认 hook 模块声明包含 `communication_context`
2. 实际 bootstrap 后的 hook registry 能按模块 stem 加载 `communication_context`
3. group relay metadata 包含真实 `participant_agent_ids`
4. Gateway session metadata 优先使用 `participant_agent_ids`，不再退化为仅 mentioned agent
5. 相关 unit / integration 测试覆盖 hook 加载与 participant 透传回归

**Tests Plan**：
- unit: `tests/unit/test_product_profiles.py` 断言默认模块与实际 registry 含 `communication_context`
- unit: `tests/unit/personal_assistant/test_gateway_pipeline.py` 覆盖 session metadata 使用真实参与者
- unit: `tests/im_service/unit/test_relay_service.py` 覆盖 relay metadata 带真实参与者
- integration: `tests/im_service/integration/test_m136_group_chat_flow.py` / `tests/im_service/integration/test_m103_im_gateway_e2e.py` 覆盖 group relay 实链路元数据
- contract/e2e: 不单独新增；由现有 IM↔Gateway 集成测试承担入口验证

**Expected Tests**：
- `tests/unit/test_product_profiles.py`
- `tests/unit/personal_assistant/test_gateway_pipeline.py`
- `tests/im_service/unit/test_relay_service.py`
- `tests/im_service/integration/test_m136_group_chat_flow.py`
- `tests/im_service/integration/test_m103_im_gateway_e2e.py`

**DoD**：`test_command` 全绿 + C1/C2/C3 + PROGRESS 写清 hook stem 过滤约束与 participant 传递证据

**状态**：DONE

---

### R2 — 修复 before_agent_start 对真实 system prompt 的追加，并完成真实日志验证

**Acceptance**：
1. before_agent_start 在 payload 未带 base prompt 时，仍能从 session metadata 读取真实 system prompt
2. group chat 最终 system prompt 同时包含原始 prompt 与 communication context
3. 集成测试能覆盖 fan-out 后的 addressed / peer relay 行为，不再卡在旧单 relay 假设
4. 修复后的 IM/Gateway 实例经过真实请求链路后，日志中能看到 `[Communication Context]`、`your_agent_id`、`group_participants`
5. TASKS / PROGRESS / dev_tasks 状态更新完整，M243 仅在真实日志验证成功后标记 DONE

**Tests Plan**：
- unit: `tests/unit/test_product_profiles.py` 增加 hook 追加真实 system prompt 的断言
- integration: `tests/im_service/integration/test_m136_group_chat_flow.py` / `tests/im_service/integration/test_m103_im_gateway_e2e.py` 修正为消费真实 group fan-out relay，并验证回执/完成行为
- e2e: 使用本地真实 IM + Gateway + kernel + mock openai_compat server 跑一次 group 请求，检查请求日志中的最终 system prompt
- contract: 不新增单独 contract；继续沿用真实请求日志作为最终契约证据

**Expected Tests**：
- `tests/unit/test_product_profiles.py`
- `tests/im_service/integration/test_m136_group_chat_flow.py`
- `tests/im_service/integration/test_m103_im_gateway_e2e.py`
- 真实验证：本 milestone 的运行日志证据

**DoD**：`test_command` 全绿 + 真实日志验证成功 + C1/C2/C3 + PROGRESS 记录证据与回滚点

**状态**：DONE（2026-03-19 fresh 日志复核通过；详见 PROGRESS）
