# TASKS (Milestone: M14)

- Test command: `pytest -q`
- Branch: `milestone/M14`

## [TODO] R14.1 read 语义补齐（图片输入 + 文本截断/offset 提示）
- Acceptance:
  - `read` 支持图片文件输入（`jpg/png/gif/webp`），返回 `content` 为 `text + image` 两段结构。
  - `read` 文本输出在触发截断时追加“下一次 offset 提示”语义，且 `next_offset` 与提示一致。
  - `read` 文本 `offset/limit` 与越界错误语义保持稳定。
  - 对文本与图片返回结构做契约保护，避免后续回归破坏。
- Tests Plan:
  - `unit`: 选。覆盖 read 文本/图片分支、截断提示、边界条件。
  - `contract`: 选。固定 `read` 返回结构（尤其 `content` list parts）。
  - `integration`: 选。覆盖 read 经过 `ToolRegistry` 执行路径的稳定性。
  - `e2e`: 不选。当前无独立 read HTTP/CLI 入口，integration 已覆盖真实工具调度入口。
- Expected Tests:
  - `tests/unit/test_tools_builtins.py`
  - `tests/contract/test_tools_read_contract.py`（新增）
  - `tests/integration/test_tools_read_integration.py`（新增）
- DoD:
  - 目标测试红转绿，且 `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - `PROGRESS/M14-*.md` 记录决策/证据/回退点/哈希。
- Status: DOING

## [TODO] R14.2 tool_result list content 保真透传
- Acceptance:
  - `tool_result` 拦截链在返回 `content` 为 list 时保持原样透传，不将 list 折叠为字符串或包装破坏结构。
  - `tool_result` 在 `content` 为 mapping/list 时行为一致且向后兼容现有 mapping 重写场景。
  - read 图片 parts 经 `tool_result` 链路仍保持 `text + image` parts 完整。
- Tests Plan:
  - `unit`: 选。覆盖 HookRunner + ToolRegistry 对 `tool_result` 的合并/透传细节。
  - `contract`: 选。固定 tool_result 重写契约（list content/mapping content）。
  - `integration`: 选。覆盖带 hook 的工具执行链路。
  - `e2e`: 不选。当前不存在直接暴露 tool_result 的独立终端入口，integration 已覆盖主入口。
- Expected Tests:
  - `tests/unit/test_hooks_runner.py`
  - `tests/contract/test_hook_integration_contract.py`
  - `tests/integration/test_m8_agent_tool_hook_r81_integration.py`
  - `tests/integration/test_tools_read_integration.py`（复用）
- DoD:
  - 目标测试红转绿，且 `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - `PROGRESS/M14-*.md` 记录决策/证据/回退点/哈希。
- Status: TODO

## [TODO] R14.3 bash 语义对齐（无默认超时 + 截断落盘 fullOutputPath）
- Acceptance:
  - `bash` 在未显式传 `timeout` 时不注入默认超时。
  - 输出过大触发截断时，返回中包含 `full_output_path`，且对应文件可读取完整输出。
  - 超时、中断（signal）与非 0 退出码路径都返回稳定错误语义且保留关键回执字段。
  - 工具返回结构保持兼容（保留 `exit_code/stdout/stderr/truncated` 基础字段）。
- Tests Plan:
  - `unit`: 选。覆盖超大输出/超时/中断/非 0 返回码。
  - `contract`: 选。固定 bash 返回字段与错误 `details` 契约。
  - `integration`: 选。覆盖 `ToolRegistry` 执行 bash 的行为一致性。
  - `e2e`: 选（回归现有）。跑工具相关 e2e 套件，确保全链路无回退。
- Expected Tests:
  - `tests/unit/test_tools_builtins.py`
  - `tests/contract/test_tools_bash_contract.py`（新增）
  - `tests/integration/test_tools_bash_integration.py`（新增）
  - `tests/e2e/test_tools_list_e2e.py`（回归）
- DoD:
  - 目标测试红转绿，且 `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - `PROGRESS/M14-*.md` 记录决策/证据/回退点/哈希。
- Status: TODO

## 续跑计划（2026-03-02）
- 当前接手分支：`milestone/M14`（`use_worktree=false`，串行执行）。
- 启动门禁：`pytest -q` 基线通过（`177 passed, 2 skipped`）。
- 执行顺序：
  - `R14.1` 先补 read 红测（图片 part + 截断/offset 提示）再实现。
  - `R14.2` 衔接 hook/tool_result 透传语义，确保 list content 不破坏。
  - `R14.3` 最后对齐 bash（无默认超时 + 截断落盘 fullOutputPath + 超时/中断）。
