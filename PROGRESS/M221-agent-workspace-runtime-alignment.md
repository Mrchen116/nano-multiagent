# M221 查明并修复 Agent workspace 显示与运行目录错乱

## Notes
- 已阅读 `LOGBOOK.md`：真实入口行为若与源码矛盾，要先确认是否存在接线层丢字段/旧默认值伪装成“有效配置”；本次重点是会话创建与 runtime cwd 真值，而不是 UI 文案。
- 已阅读 `COMMENTING_GUIDE.md`：后续 public API/docstring 与注释只写契约、边界和为什么，不复述实现。
- 基线门禁当前已有 1 个既有失败：`tests/e2e/test_personal_assistant_main_e2e.py::test_main_stop_command_reports_still_healthy_when_another_listener_remains` 健康检查超时；先作为 baseline 记录，待本 milestone 收尾时对比是否新增/消除。

## Roadpoint Records

### R1 固化 workspace 设置未进入 kernel session / runtime cwd 的红测
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py tests/e2e/test_personal_assistant_main_e2e.py -q`
  - Entry: 待补
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 先补红测锁定 workspace 在 session/runtime 何处丢失。

### R2 修复会话创建、runtime 上下文与 config resolver 的 workspace 真源
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py tests/e2e/test_personal_assistant_main_e2e.py -q`
  - Entry: 待补
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 待 R1 根因锁定后实施最小修复。

### R3 用真实创建与真实运行态完成回归验证并收口文档
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py tests/e2e/test_personal_assistant_main_e2e.py -q`
  - Entry: 待补
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 待实现后回填真实 runtime 验证与收尾信息。
