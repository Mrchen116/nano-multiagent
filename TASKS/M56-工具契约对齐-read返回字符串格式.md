# M56 - 工具契约对齐（read 返回字符串格式）

## Milestone Contract
- milestone_id: `M56`
- title: `工具契约对齐-read 返回字符串格式`
- goal: `将 read 工具返回格式与《内核设计细化/工具设计细化.md》一致，特别是 text/image content 与截断提示字符串。`
- execution_mode: `parallel`
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M56`
- branch: `milestone/M56`
- test_command: `PYTHONPATH=src pytest -q tests/unit/test_tools_builtins.py tests/contract/test_tools_read_contract.py tests/integration/test_tools_read_integration.py`
- dev_tasks_path: `data/dev-tasks.json`（worktree 内 symlink 到主仓共享文件）
- allowed_scope:
  - `src/nano_multiagent/tools/builtins/read.py`
  - `src/nano_multiagent/llm/protocols/anthropic/mapper.py`（仅 image part 兼容）
  - `src/nano_multiagent/llm/protocols/openai_compat/mapper.py`（仅 image part 兼容）
  - `tests/unit/test_tools_builtins.py`
  - `tests/contract/test_tools_read_contract.py`
  - `tests/integration/test_tools_read_integration.py`
  - `TASKS/PROGRESS/LOGBOOK` 里程碑文档
- forbidden_scope:
  - `src/nano_multiagent/cli/**`
  - `src/nano_multiagent/tools/builtins/bash.py`
  - `src/nano_multiagent/tools/builtins/edit.py`
  - `src/nano_multiagent/tools/builtins/write.py`
  - `src/nano_multiagent/tools/builtins/task.py`
- prevention_rules:
  - 严格执行 C1/C2/C3。
  - 仅解决 M56，不做额外重构。
  - 忽略并保留并行改动，不回滚无关文件。

## Startup Checklist
- [x] 已阅读 `LOGBOOK.md`
- [x] 已阅读 `COMMENTING_GUIDE.md` 并承诺遵守
- [x] 已确认工作区：`milestone/M56` @ `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M56`
- [x] 已确认 `data/dev-tasks.json` 与 `data/locks` 为主仓共享 symlink
- [x] 已跑基线门禁（存在 1 个 `bash` 相关既有失败，超出 M56 范围）

## Roadpoints

### R1 文本 read 契约与截断提示对齐
- Acceptance:
  - `read` 文本返回改为 `content=[{type:text,text:...}]`。
  - 截断提示文案对齐：`Showing lines...` / `KB limit` / `remaining lines`。
  - 首行超字节阈值返回 `Use bash: sed -n ... | head -c ...` 引导语。
  - `offset` 越界错误与 `details` 字段契约可观测。
- Tests Plan:
  - unit: 选；覆盖 offset/limit/截断边界与首行超限。
  - contract: 选；覆盖返回结构与提示字符串契约。
  - integration: 选；覆盖 registry 链路下文本 read 契约。
  - e2e: 不选（本 Milestone 不涉及 CLI/HTTP 入口改动）。
- Expected Tests:
  - `tests/unit/test_tools_builtins.py`（`test_read_*`）
  - `tests/contract/test_tools_read_contract.py`（文本契约新增/改造）
  - `tests/integration/test_tools_read_integration.py`（文本链路新增/改造）
- DoD:
  - R1 相关红测先失败，随后实现通过。
  - `test_command` 全绿（记录基线已知失败边界与最终结果）。
  - C1/C2/C3 提交齐全，PROGRESS 记录决策/证据/回退点。
- Status: `TODO`

### R2 图片 read part 与 mapper 兼容对齐
- Acceptance:
  - `read` 图片返回 `text + image` parts，image part 含 `data` 与 `mimeType`。
  - 文本 note 对齐 `Read image file [mime]`，包含尺寸提示语义。
  - anthropic/openai_compat mapper 兼容 read 新 image part。
  - contract+integration 验证 hook rewrite 后 part 结构不丢失。
- Tests Plan:
  - unit: 选；覆盖 `ReadTool` 图片 part 字段与文本 note。
  - contract: 选；覆盖图片返回字段契约。
  - integration: 选；覆盖 registry/hook 链路结构保真。
  - e2e: 不选（不涉及端到端入口）。
- Expected Tests:
  - `tests/unit/test_tools_builtins.py::test_read_returns_text_and_image_parts_for_png`
  - `tests/contract/test_tools_read_contract.py::test_read_image_contract_returns_text_plus_image_parts`
  - `tests/integration/test_tools_read_integration.py::test_read_image_parts_survive_tool_result_content_rewrite`
- DoD:
  - R2 红测先失败并明确缺失点。
  - 实现后 `test_command` 全绿。
  - C1/C2/C3 提交齐全。
- Status: `TODO`

## Delivery Notes
- 本 Milestone 以 read 工具契约为唯一目标；不触碰 bash/edit/write/task 实现。
