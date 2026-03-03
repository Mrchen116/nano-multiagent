# TASKS (Milestone: M27)

- Test command: `pytest -q`
- Branch: `milestone/M27`
- Milestone status: `RUNNING`
- Refactor boundaries:
  - Must keep unchanged: CLI HTTP-only 调用路径、单命令模式 JSON 契约、现有 REPL 命令执行语义。
  - Allowed to change: `src/nano_multiagent/cli/**` 的可编辑输入实现与 REPL 交互增强测试。

## [DONE] R27.1 在输入引擎实现“/ 触发命令下拉 + ↑/↓选择 + Enter填充”
- Acceptance:
  - 可编辑输入模式下，输入 `/` 时展示命令候选（至少 `/help /new /use /session /tools /compact /history /exit`）。
  - 下拉打开时，`↑/↓` 仅切换候选选中项，不触发历史回填。
  - 下拉打开时按 `Enter` 会把选中命令填充到输入框（不立即提交执行）。
  - 下拉关闭后，行内编辑（`←/→`、Backspace）与历史回填行为保持可用。
- Tests Plan:
  - `unit`: 选。覆盖输入引擎按键行为与下拉状态切换边界。
  - `contract`: 不选。不涉及 HTTP 字段/协议变更。
  - `integration`: 选。验证 REPL 真实入口下命令填充与后续执行链路。
  - `e2e`: 不选。当前增强聚焦 CLI 输入层，integration 已覆盖入口行为。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py`
- DoD:
  - `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - PROGRESS 记录决策/证据/回滚点/提交哈希。
- Commits:
  - C1: `f75ad20`
  - C2: `5308b13`
  - C3: `f072de3`
- Status: DONE

## [DONE] R27.2 在 REPL 编排层接线并补充边界门禁
- Acceptance:
  - `_run_repl` 调用输入引擎时注入命令候选来源，且与 `supported_repl_commands()` 对齐。
  - 历史回填链路不被命令下拉污染（例如 `↑` 仍可回填上一条普通输入）。
  - 单命令入口（如 `send-message`）输出保持纯 JSON，不受交互增强影响。
  - 文档与门禁测试覆盖“斜杠触发 + 选择填充 + 命令执行”主路径。
- Tests Plan:
  - `unit`: 选。覆盖接线行为与输入/历史兼容回归。
  - `contract`: 选。复跑现有 CLI 契约，确认 JSON 契约稳定。
  - `integration`: 选。验证 REPL 主链路（编辑输入 -> 命令执行）无回归。
  - `e2e`: 不选。无新增跨进程部署行为。
- Expected Tests:
  - `tests/unit/test_cli_refactor_boundaries.py`
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py`
  - `tests/contract/test_cli_http_only_contract.py`
- DoD:
  - `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - PROGRESS 记录决策/证据/回滚点/提交哈希。
- Commits:
  - C1: `1a932c6`
  - C2: `ec75ebe`
  - C3: `<pending>`
- Status: DONE
