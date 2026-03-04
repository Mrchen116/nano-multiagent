# M62 Codex CLI研究三期（TTY/non-TTY契约与交互可观测）

日期：2026-03-04
分支：`milestone/M62`
工作区：`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M62`

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `113 passed, 42 warnings`

### Plan（一次性拆分）
- Context:
  - M62 属于研究型里程碑，目标是形成可执行契约与测试矩阵，不涉及实现代码。
  - 必须与蓝图边界一致：仅 CLI 研究与文档沉淀，不触碰内核/API 代码。
- Decision:
  - 拆分三轮研究：R1 输出边界、R2 折叠/错误/观测、R3 契约模板与测试矩阵。
  - 每轮都要求“新问题 -> 代码锚点 -> 迁移规则”。
- Rationale:
  - 按问题驱动分轮可以避免大而泛综述，保证后续里程碑可直接消费。
- Evidence:
  - Tests: baseline `113 passed, 42 warnings`。
  - Entry: 关键前置文档（LOGBOOK/蓝图/M44补充）已完成阅读。
- Rollback:
  - 回退到计划提交前稳定点。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1 第一轮探索：定位 codex 的 TTY/non-TTY 判定与输出路径分叉点。

### R1 TTY/non-TTY 输出边界研究（规则 + 反例 + 代码锚点）
- Context:
- 目标是把 codex 的输出通道边界提炼为可迁移规则，避免 nano CLI 在脚本态污染 stdout 或在非 TTY 场景输出不可机读噪音。
- 仅研究与文档落盘，不改 nano 实现代码。
- Decision:
- 采用三轮问题驱动（`R1.Q1~Q3`）梳理：通道契约、TTY 判定、反例与迁移约束。
- 形成 `TTY边界规则`、`non-TTY反例`、`迁移约束` 三件套，供 M52 直接消费。
- Rationale:
- `exec` 与 `interactive TUI` 的边界都依赖 stdin/stderr 是否为 TTY；必须先明确“什么写 stdout、什么写 stderr”，否则后续商业化契约无法落地。
- Evidence:
  - Tests:
    - 红测：`rg -n '^#### R1\\.Q1|^#### R1\\.Q2|^#### R1\\.Q3' PROGRESS/M62-Codex-CLI研究三期-TTY非TTY契约与交互可观测.md` → `R1_RED_EXIT=1`（变更前）。
    - 绿测：`rg -n '^#### R1\\.Q1|^#### R1\\.Q2|^#### R1\\.Q3' ... && rg -n 'TTY边界规则|non-TTY反例|迁移约束' ...` 命中通过。
    - 基线：`PYTHONPATH=src pytest -q ...` → `113 passed, 42 warnings`。
  - Entry:
    - 代码锚点来源：`/Users/czj/Repos/opencode-hub/codex/codex-rs/exec/src/lib.rs`、`.../event_processor_with_human_output.rs`、`.../event_processor_with_jsonl_output.rs`、`.../cli/src/main.rs`。
- Rollback:
- 回退到 `d413aef`（R1 C1）。
- Commits: C1=`d413aef`, C2=`848bd93`, C3=`TBD`
- Next:
- 进入 R2：先补“状态折叠/错误分层/观测指标”文档红测校验命令（C1）。

#### R1.Q1 默认输出模式如何保证“脚本可机读 + 人类可读”不冲突？
- 结论：
  - codex 在文件头明确约束：默认模式 `stdout` 只能有 final message；`--json` 模式 `stdout` 必须是 JSONL；其他输出统一走 `stderr`。
  - 通过 `#![deny(clippy::print_stdout)]` 从编译期限制“误写 stdout”。
  - 人类模式事件文本由 `ts_msg!`（`eprintln!`）输出，最终消息在收口阶段单独写入 `stdout`。
- 代码锚点：
  - `exec/src/lib.rs:1-5`
  - `exec/src/lib.rs:342-350`
  - `exec/src/event_processor_with_human_output.rs:164-169`
  - `exec/src/event_processor_with_human_output.rs:862-883`
  - `exec/src/event_processor_with_jsonl_output.rs:846-853`

#### R1.Q2 TTY 判定在哪些入口影响行为？
- 结论：
  - `exec` 模式的提示词读取在 `resolve_prompt` 中根据 `stdin.is_terminal()` 分岔：TTY 且未显式 `-` 时拒绝并退出，管道输入才读取 stdin。
  - `interactive` 模式在 `TERM=dumb` 且 `stdin/stderr` 非 TTY 时直接 fatal，避免无终端确认导致假启动。
  - 光标进度条能力由 `stderr ANSI/TTY + TERM` 联合判定，非 TTY 时降级为普通换行输出。
- 代码锚点：
  - `exec/src/lib.rs:856-892`
  - `cli/src/main.rs:899-915`
  - `exec/src/lib.rs:131-148`
  - `exec/src/event_processor_with_human_output.rs:989-1025`

#### R1.Q3 迁移到 nano CLI 前必须防的误用有哪些？
- TTY边界规则（6条）：
  - 规则1：默认模式 `stdout` 仅承载 final message，其他过程信息必须走 `stderr`（`exec/src/lib.rs:1-5`）。
  - 规则2：JSON 模式 `stdout` 只能输出 JSONL 事件行，不得掺杂提示文案（`exec/src/lib.rs:3-4`, `.../event_processor_with_jsonl_output.rs:846-853`）。
  - 规则3：human 模式工具过程与状态信息走 `stderr`，final message 在收口后一次输出（`.../event_processor_with_human_output.rs:164-169`, `862-883`）。
  - 规则4：无 prompt 且 stdin 为 TTY 时必须失败退出，不得隐式阻塞读 stdin（`exec/src/lib.rs:862-867`）。
  - 规则5：`TERM=dumb` + 非 TTY 下拒绝启动交互 TUI（`cli/src/main.rs:900-905`）。
  - 规则6：光标/ANSI 进度仅在具备终端能力时启用，非 TTY 必须退化为纯文本行输出（`exec/src/lib.rs:131-148`, `.../event_processor_with_human_output.rs:989-995`）。
- non-TTY反例（至少4条）：
  - 反例1：在 JSON 模式往 `stdout` 打 `warning:`/`debug` 文案，会直接污染 JSONL 下游解析（锚点同规则2）。
  - 反例2：在 non-TTY 日志通道输出 ANSI 光标控制符，会导致 CI 日志出现转义残片与错位（`.../event_processor_with_human_output.rs:1006-1014`）。
  - 反例3：脚本调用未传 prompt 且 stdin 仍是 TTY，若不立即失败会出现不可控阻塞（`exec/src/lib.rs:862-867`）。
  - 反例4：`TERM=dumb` 场景强行起交互 TUI，在无 tty 确认能力时会形成“不可确认”的死分支（`cli/src/main.rs:900-914`）。
  - 反例5：把工具实时过程与最终摘要都写到 stdout，会破坏“单命令机读契约”。
- 迁移约束（映射 nano CLI / M52）：
  - 约束1：建立“双通道输出契约”：`stdout=可机读终值`，`stderr=过程/诊断`，并在 send-message 场景强制执行。
  - 约束2：在 CLI 入口显式区分 `stdin.isatty()` 与 `--prompt -`，禁止隐式等待 stdin。
  - 约束3：所有 cursor/ANSI 功能必须以 `stderr 是否 tty + TERM` 为门控，并有无 ANSI 回退分支。
  - 约束4：任何新增日志默认写 stderr；若确需 stdout，必须先证明不破坏 JSON 契约。
  - 约束5：把“模式分支（human/json）”前置到事件处理器构造阶段，避免运行中混写。

### R2 状态行/事件折叠 + 错误分层 + 可观测指标研究
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R3 商业化前契约模板 + M52/M53/M54 测试矩阵草案
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
