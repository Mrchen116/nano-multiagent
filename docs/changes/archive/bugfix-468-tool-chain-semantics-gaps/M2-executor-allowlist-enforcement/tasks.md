# bugfix-468-M2: executor-allowlist-enforcement — Tasks

> 对齐: ../design.md v1

## 目标

让主会话的显式 `tool_allowlist`（含空名单）在执行层真正生效：
- 显式空名单会话里，任何模型自由发挥的工具调用都被拒绝且不产生副作用；
- 显式非空名单会话里，名单内工具正常执行，名单外工具被拒绝；
- `tool_allowlist=None` 的会话（CLI / kernel 默认）行为不变，仍 unrestricted。

## 退出标准

- [x] `src/agent/core/agent/runtime.py` 的 `_execute_loop` 在 `session.config.tool_allowlist is not None` 时，把可用工具名字集传给 `loop.run(tool_execution_allowlist=...)`；为 `None` 时传 `None`。
- [x] `src/agent/core/agent/tool_executor.py` 非名单工具拒绝文案使用 `tool '<name>' is not enabled in this session`。
- [x] 三类单测齐：显式空名单→全拒（含无副作用断言）、显式名单→名单内可执行+名单外拒绝、None→不限制。
- [x] `pytest tests/unit/agent tests/unit/personal_assistant -q` 全绿。
- [x] 真栈证据：用 `scripts/e2e-up.sh` 起隔离栈，配置一个 `tool_allowlist=[]` 的 agent，诱导工具调用，验证 IM 消息里出现拒绝反馈、无文件副作用、agent 能文本回复；证据落 `evidence/`。

## 测试策略

- 被测行为（来自退出标准）：
  1. 显式空名单会话调用任何工具都被执行层拒绝，且拒绝文案含工具名与 "not enabled in this session"。
  2. 显式非空名单会话仅允许名单内工具执行；名单外工具被拒绝。
  3. `tool_allowlist=None` 时不限制工具执行。
  4. runtime 把 session config 的显式名单贯通到 `loop.run(tool_execution_allowlist=...)`。
- 已有测试在：`tests/unit/test_streaming_tool_executor.py`（扩展），理由：executor 的 allowlist 拦截与拒绝文案已有 feat-440-M2 相关用例，新增主会话显式名单/空名单/None 用例最自然；`tests/unit/agent/` 下新建 `test_runtime_tool_allowlist_enforcement.py`，理由：runtime→loop 的 allowlist 接线没有现成覆盖，需用 `AgentEngine.execute_turn` + `ConversationSession` 走一次完整 turn。
- 落层/目录/marker：`tests/unit/`（纯逻辑/单模块 + 跨模块但无真实进程），无 marker。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：`evidence/e2e-allowlist-empty.json`（真栈消息记录）。

## Roadpoints

### R1 — executor + runtime allowlist enforcement (DONE)

- 步骤:
  - C1: 在 `test_streaming_tool_executor.py` 补显式空名单/非空名单/None 三类用例；新建 `test_runtime_tool_allowlist_enforcement.py` 验证 runtime 贯通。
  - C2: 改 `tool_executor.py` 拒绝 reason；改 `runtime.py` `_execute_loop` 传 `tool_execution_allowlist`。
  - C3: 补 `progress.md` 证据段；跑全测试树；收集真栈证据。
- 验证:
  - 三类单测红→绿。
  - `pytest tests/unit/agent tests/unit/personal_assistant -q` 全绿。
  - `scripts/e2e-up.sh` 真栈验证空名单拒绝。
