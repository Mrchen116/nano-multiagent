# M28 注释补齐A：core/llm/agent（含compaction）

## Milestone 目标
按 `COMMENTING_GUIDE.md` 为 `core/llm/agent(+compaction)` 补齐 public API docstring 与关键约束注释，确保调用契约、失败语义、边界约束与蓝图一致，且行为保持不变。

## 约束与边界
- 仅改注释/docstring，不改运行行为。
- 仅改动允许范围：`src/nano_multiagent/core/**`、`src/nano_multiagent/llm/**`、`src/nano_multiagent/agent/**`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`、`data/dev-tasks.json`。
- 注释只解释 why/约束/边界/代价，不复述代码流程。

## Roadpoints

### R28.1 core + llm public API docstring 补齐
- Status: DONE
- Acceptance:
  - `core/*` 与 `llm/*` 的 public module/class/function/method 补齐 docstring。
  - docstring 与真实行为一致，按需含 `Args/Returns/Raises/Side Effects`。
  - provider 相关边界在注释中强调“隔离在 llm/protocols，runtime 不感知协议细节”。
  - 不引入行为变更。
- Tests Plan:
  - unit: 不新增（本里程碑仅注释改动，现有单测覆盖行为回归）。
  - contract: 不新增（不改协议结构）。
  - integration: 不新增（不改接线逻辑）。
  - e2e: 不新增（不改入口行为）。
  - 选择理由：以全量回归 `PYTHONPATH=src pytest -q` 作为行为保持门禁。
- Expected Tests:
  - `PYTHONPATH=src pytest -q`
  - docstring 覆盖自检脚本（AST 扫描 public 定义是否缺失 docstring）。
- DoD:
  - 完成 C1/C2/C3。
  - `PYTHONPATH=src pytest -q` 全绿。
  - PROGRESS 写清决策/证据/提交哈希。

### R28.2 agent(+compaction) public API docstring + 蓝图关键约束注释
- Status: DOING
- Acceptance:
  - `agent/*` 与 `agent/compaction/*` public API docstring 补齐。
  - 为关键约束补块注释：
    - provider 隔离边界（runtime/loop 不直接耦合 provider 协议细节）。
    - compaction 切点不拆 `tool-call/tool-result` 对。
    - runtime loop 边界与策略（何时终止、何时 fail-open、何时触发压缩重试）。
  - 不新增复述代码式注释。
  - 不引入行为变更。
- Tests Plan:
  - unit: 不新增（行为不变）。
  - contract: 不新增（接口语义未改）。
  - integration: 不新增（链路逻辑未改）。
  - e2e: 不新增（入口行为未改）。
  - 选择理由：全量门禁验证“注释改动不破坏行为”。
- Expected Tests:
  - `PYTHONPATH=src pytest -q`
  - docstring 覆盖自检脚本（AST 扫描）。
- DoD:
  - 完成 C1/C2/C3。
  - `PYTHONPATH=src pytest -q` 全绿。
  - PROGRESS 写清决策/证据/提交哈希。
