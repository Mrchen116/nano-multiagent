# M226 Gateway本地配置模型扩展与YAML持久化

## Roadpoints

### R1 扩展 AgentWorkspaceConfig 字段并解析
- Acceptance:
  1. AgentWorkspaceConfig 包含 system_prompt/group_reply_policy/default_model（可选，默认 None）
  2. _parse_agents 解析所有六个可选字段（skills/tool_allowlist/system_prompt/group_reply_policy/default_model）
  3. 无新字段的旧 YAML 仍正常加载（向后兼容）
  4. 新字段从 YAML 正确读入
  5. 现有测试全绿
- Tests Plan:
  - unit: 测试新字段默认值、从 YAML 加载含新字段、不含新字段向后兼容
  - contract/integration/e2e: 不需要，纯数据模型层
- Expected Tests:
  - tests/unit/personal_assistant/test_local_store.py::test_parse_agents_loads_extended_fields
  - tests/unit/personal_assistant/test_local_store.py::test_parse_agents_defaults_new_fields_to_none
- DoD: test_command 全绿 + C1/C2/C3 齐全
- Status: TODO

### R2 save_local_config 序列化落盘 + round-trip
- Acceptance:
  1. save_local_config 将 LocalConfig 序列化为 YAML 并写入指定路径
  2. load -> save -> load round-trip 产出等价 config
  3. 序列化 YAML 包含所有扩展字段
  4. None 字段不写入 YAML（保持简洁）
  5. 现有测试全绿
- Tests Plan:
  - unit: round-trip 测试、序列化输出验证
  - contract/integration/e2e: 不需要
- Expected Tests:
  - tests/unit/personal_assistant/test_local_store.py::test_save_local_config_round_trip
  - tests/unit/personal_assistant/test_local_store.py::test_save_local_config_omits_none_fields
- DoD: test_command 全绿 + C1/C2/C3 齐全
- Status: TODO
