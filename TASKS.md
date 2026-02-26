# TASKS (Current Milestone: M4)

## [DONE] R4.1 agent 核心状态机模块最小实现
- Steps:
  - 先新增 `state/policies/prompting/loop` 的 unit/contract 失败测试（Red）
  - 实现 `agent/state.py` 支持 `text/image` parts 解析与 image 占位文本渲染
  - 实现 `agent/policies.py` 最大轮次与上下文裁剪策略
  - 实现 `agent/prompting.py` 和 `agent/loop.py` 串联上下文构建与 LLM 调用
  - 运行目标测试并记录证据
- Expected Tests:
  - `tests/unit/test_agent_state.py`
  - `tests/unit/test_agent_policies.py`
  - `tests/unit/test_agent_prompting.py`
  - `tests/unit/test_agent_loop.py`
  - `tests/contract/test_agent_state_contract.py`
- DoD:
  - 目标测试全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R4.1 hash 与证据

## [DONE] R4.2 runtime 接线与事件落盘闭环验证
- Steps:
  - 新增 runtime 闭环的 unit/contract/integration/e2e 失败测试（Red）
  - 实现 `agent/runtime.py`，打通 text parts -> context -> LLM -> assistant 文本
  - 在 `session.entries/manager` 增补 turn 事件构造与历史重建接口
  - 验证运行结果落 `TURN_APPENDED` 事件，并支持下一轮基于历史上下文推理
  - 跑全量 `pytest -q`，更新四文档并回填 `PENDING-C3-*`
- Expected Tests:
  - `tests/unit/test_agent_runtime.py`
  - `tests/contract/test_agent_runtime_contract.py`
  - `tests/integration/test_agent_runtime_integration.py`
  - `tests/e2e/test_agent_runtime_e2e.py`
  - `pytest -q`
- DoD:
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R4.2 hash 与事件落盘证据
  - R4.1/R4.2 文档 hash 回填完成，无占位残留

## Milestone M4 状态
- R4.1 与 R4.2 已完成，M4 Exit Criteria 达成。
