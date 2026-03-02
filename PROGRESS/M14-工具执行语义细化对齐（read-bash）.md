# PROGRESS (Milestone: M14)

- Title: 工具执行语义细化对齐（read/bash）
- Goal: 将 `read` 与 `bash` 的执行/返回语义补齐到《内核设计细化/工具设计细化.md》要求，消除图片读取、输出截断与 fullOutputPath 等高风险偏差。
- Exit Criteria:
  - `read` 支持图片输入并返回 `text+image` 结构；文本截断与 offset 提示语义通过 contract/integration 验证。
  - `tool_result` 对 list content 透传语义稳定，不再破坏 `read` 图片 parts。
  - `bash` 对齐“无默认超时”与“截断落盘 + fullOutputPath”契约，并覆盖超大输出/超时/中断测试。
  - `pytest -q` 全绿，且工具相关 e2e/contract 回归通过。
- Test command: `pytest -q`
- Branch: `milestone/M14`

### Baseline
- Context:
  - 按执行要求先读取 `LOGBOOK.md`，当前仅有 hook 加载断言稳健性规则，与 M14 直接冲突为无。
  - M14 允许改动范围：`src/nano_multiagent/tools/**`、`src/nano_multiagent/agent/runtime.py` 中 `tool_result` 相关最小改动、M14 相关 tests 与文档。
  - M14 禁止范围：与 M14 无关的 provider/runtime/session 大范围改动。
- Evidence:
  - Tests: `pytest -q` -> `177 passed, 2 skipped`
  - Entry: 当前基线全绿，可直接进入 Roadpoint 红测驱动。
- Next:
  - R14.1

### 续跑接手（2026-03-02）
- Context:
  - 接手输入契约确认：`execution_mode=serial`、`use_worktree=false`、`branch=milestone/M14`、`test_command=pytest -q`。
  - `data/dev-tasks.json` 中 M14 当前为 READY，按续跑要求在本分支继续执行并最终收口。
  - 本次接手未发现 `prevention_rules` 注入项，仅沿用 `LOGBOOK.md` 现有规则。
- Decision:
  - 保持既有三 Roadpoint 拆分不变，按 `R14.1 -> R14.2 -> R14.3` 顺序执行 C1/C2/C3。
- Rationale:
  - 三项 exit criteria 分别对应 read/tool_result/bash，串行推进可减少交叉回归。
- Evidence:
  - Tests: `pytest -q`（本次接手复跑）=`177 passed, 2 skipped`
  - Entry: 代码基线可复现，全量门禁稳定。
- Rollback:
  - `cf66bd8`（handoff docs）可作为续跑前稳定点。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:
  - R14.1 Red

### Handoff
- Context:
  - 用户中止当前执行并要求控制塔切换新执行者续跑 M14。
  - 当前仅完成 Plan 阶段，尚未进入任一 Roadpoint 的 C1 Red。
- Evidence:
  - Stable commit: `33eee54`（包含 TASKS/PROGRESS 计划骨架）
  - `data/dev-tasks.json`: `M14` 已从 `RUNNING` 释放为 `READY`（`claimed_by=null`）。
- Rollback:
  - 新执行者从 `33eee54` 继续即可；无需额外回退。
- Next:
  - 新执行者从 R14.1 开始执行 C1（先写红测）。

### R14.1 read 语义补齐（图片输入 + 文本截断/offset 提示）
- Context:
  - 现状仅支持 UTF-8 文本读取；读取图片直接触发 `UnicodeDecodeError`，且文本截断后无 next offset 提示。
  - 目标是让 `read` 对图片返回 `text+image` parts，并让文本截断结果可直接指导下一次分段读取。
- Decision:
  - 在 `ReadTool` 中加入图片后缀识别（jpg/jpeg/png/gif/webp），图片分支返回 `content=[text_part, image_part]`。
  - 文本分支在触发截断且可继续读取时追加 `[output truncated; continue with offset=<next>]` 提示。
  - 对非 UTF-8 且非支持图片类型文件返回明确 `ToolError`，避免底层解码异常上浮。
- Rationale:
  - 图片结构直接对齐细化设计并可被 hook/tool_result 链路消费。
  - 提示文案与 `next_offset` 对齐，减少模型二次推断偏差，提升分段续读稳定性。
- Evidence:
  - Tests:
    - Red: `pytest -q tests/unit/test_tools_builtins.py tests/contract/test_tools_read_contract.py tests/integration/test_tools_read_integration.py`（6 failed，验证缺口）
    - Green: `pytest -q tests/unit/test_tools_builtins.py tests/contract/test_tools_read_contract.py tests/integration/test_tools_read_integration.py`（17 passed）
    - Gate: `pytest -q`（183 passed, 2 skipped）
  - Entry:
    - `ToolRegistry.execute("read", {"path":"pixel.png"})` 返回 `text+image` 两段结构；
    - 截断文本输出包含 `offset=<next_offset>` 提示且 `next_offset` 同步更新。
- Rollback:
  - `1010408`（R14.1 测试红测提交）
- Commits: C1=1010408, C2=9a99b2c, C3=94f2407
- Next:
  - R14.2 Red：补 `tool_result` list content 透传红测。

### R14.2 tool_result list content 保真透传
- Context:
  - `tool_result` 拦截结果中 `content` 为 list 时，`ToolRegistry.execute` 当前会包装成 `{"result": [...]}`，导致调用方失去 `content` 语义。
  - R14.1 的 `read` 图片返回依赖 `content` parts，经过 hook 重写链路后需要保持结构不变。
- Decision:
  - 在 `ToolRegistry.execute` 中对 `content` 分支新增 list 特判：返回 `{"content": content}`。
  - 保持原有 mapping 分支行为（mapping 仍直接展开返回），避免破坏既有 `{"content": {"text": ...}}` 契约。
- Rationale:
  - 该改动是最小链路修复，只触及 `tool_result` 返回归一化逻辑，风险低且覆盖面可控。
- Evidence:
  - Tests:
    - Red: `pytest -q tests/contract/test_hook_integration_contract.py tests/integration/test_m8_agent_tool_hook_r81_integration.py tests/integration/test_tools_read_integration.py`（3 failed，全部为 list content 被包成 `result`）
    - Green: 同命令（12 passed）
    - Gate: `pytest -q`（186 passed, 2 skipped）
  - Entry:
    - `tool_result` hook 返回 list content 时，`ToolRegistry.execute` 产物为 `{"content": [...]}`；
    - `read` 图片 parts 经 `tool_result` 重写后结构保持 `text+image`。
- Rollback:
  - `9f7238c`（R14.2 红测提交）
- Commits: C1=9f7238c, C2=d7812ae, C3=5ca3211
- Next:
  - R14.3 Red：覆盖 bash 无默认超时、截断落盘与 fullOutputPath、超时/中断语义。

### R14.3 bash 语义对齐（无默认超时 + 截断落盘 fullOutputPath）
- Context:
  - `ToolSafety.run_command` 会在未传 `timeout` 时注入默认 30s，违背“bash 无默认超时”目标语义。
  - 截断路径仅返回截断后的 `stdout/stderr`，未暴露全量日志文件路径，无法追溯完整输出。
  - 进程被 signal 终止时统一报“non-zero status”，缺失 `signal/signal_number` 细节。
- Decision:
  - 将 bash 执行超时语义改为“仅当调用方显式传入 `timeout` 才启用 subprocess timeout”。
  - 截断发生时持久化完整输出到 `<repo_root>/.nano_multiagent/tmp/bash-output-*.log`，并在结果/错误细节里返回 `full_output_path`。
  - 对 `exit_code < 0` 场景输出稳定错误文案 `terminated by signal`，并补齐 `signal` 与 `signal_number` details。
- Rationale:
  - 最小改动即可对齐设计细化约束，同时保持 `exit_code/stdout/stderr/truncated` 原字段兼容。
  - 把 full output 落盘放在 `ToolSafety` 层可复用同一截断判定，降低工具层重复逻辑。
- Evidence:
  - Tests:
    - Red: `pytest -q`（6 failed，全部聚焦 bash 的 `full_output_path` / no-default-timeout / signal 语义）
    - Green: `pytest -q tests/unit/test_tools_builtins.py tests/contract/test_tools_bash_contract.py tests/integration/test_tools_bash_integration.py`（20 passed）
    - Gate: `pytest -q`（193 passed, 2 skipped）
  - Entry:
    - `BashTool` 截断输出返回 `full_output_path`，文件可读取完整日志；
    - signal 终止时错误消息包含 `terminated by signal`，details 含 `signal/signal_number`。
- Rollback:
  - `c5e746a`（R14.3 红测提交）
- Commits: C1=c5e746a, C2=277f9c9, C3=<pending>
- Next:
  - Milestone 收口：rebase `origin/main`、全量门禁、merge main、更新 `data/dev-tasks.json` 为 DONE。
