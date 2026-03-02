# TASKS (Milestone: M24)

- Test command: `pytest -q`
- Branch: `milestone/M24`
- Milestone status: `RUNNING`
- Refactor boundaries:
  - Must keep unchanged: CLI HTTP-only call path、REPL命令语义/错误文本、输入编辑行为（光标移动/历史回填）、现有测试期望。
  - Allowed to change: `cli` 内部文件布局、函数归属、模块边界、薄编排调用方式。

## [TODO] R24.1 抽离可编辑输入与历史回填引擎到 `cli/repl_input.py`
- Acceptance:
  - `commands.py` 中终端输入编辑相关实现（raw mode/key 读取/行内编辑/历史回填）迁移到独立模块。
  - `commands.py` 仅保留对输入引擎的调用，不再承载输入细节分支。
  - 行为保持一致：↑/↓ 历史回填、←/→ 光标移动、行内插入/删除、EOF/中断处理不变。
  - 新增边界测试确保输入引擎模块职责稳定，防止逻辑回流 `commands.py`。
- Tests Plan:
  - `unit`: 选。覆盖输入引擎模块入口、现有行内编辑行为回归。
  - `contract`: 不选。不涉及 HTTP 字段/协议变更。
  - `integration`: 选。复用 CLI 交互链路用例，确保入口行为无漂移。
  - `e2e`: 不选。该重构不引入外部部署差异，integration 足够覆盖入口。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py`
  - `tests/unit/test_cli_refactor_boundaries.py`（新增）
- DoD:
  - `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - PROGRESS 记录决策/证据/回滚点/提交哈希。
- Commits:
  - C1: `<pending>`
  - C2: `<pending>`
  - C3: `<pending>`
- Status: TODO

## [TODO] R24.2 抽离 REPL 命令路由与参数校验到 `cli/repl_commands.py`
- Acceptance:
  - `/help /new /use /session /tools /compact /history /exit` 的路由/参数校验迁移到独立模块。
  - `commands.py` 的 `_run_repl` 只保留主循环编排（读输入、委派命令、发送消息、错误兜底）。
  - 命令错误输出（Error/Layer/Suggestion/Usage）与成功输出格式保持一致。
  - 新增边界测试确保命令分发职责在新模块，避免回归为单文件巨函数。
- Tests Plan:
  - `unit`: 选。覆盖命令分发与参数校验行为及委派边界。
  - `contract`: 不选。无新增 API 契约字段。
  - `integration`: 选。覆盖 CLI->HTTP 命令链路不变。
  - `e2e`: 不选。入口行为已由 integration 覆盖。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py`
  - `tests/unit/test_cli_refactor_boundaries.py`
- DoD:
  - `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - PROGRESS 记录决策/证据/回滚点/提交哈希。
- Commits:
  - C1: `<pending>`
  - C2: `<pending>`
  - C3: `<pending>`
- Status: TODO
