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
- M53 需要把“实时状态线 + 事件折叠 + 错误提示 + 指标采样”一次性收敛，否则会出现重复刷屏、错误语义混层、排障不可观测。
- Decision:
- 仍采用三轮追问（`R2.Q1~Q3`）：先识别状态门控，再抽象错误分层，最后给可观测指标与采样位点。
- 以 codex 的 `EventProcessor` 生命周期与 JSON/human 双处理器为锚点，映射到 nano CLI 契约草图。
- Rationale:
- codex 已在事件层实现“静默事件折叠 + 进度行中断 + begin/end 配对容错”，可直接转化为 nano 的可落地规则。
- Evidence:
  - Tests:
    - 红测：`rg -n '^#### R2\\.Q1|^#### R2\\.Q2|^#### R2\\.Q3' PROGRESS/M62-Codex-CLI研究三期-TTY非TTY契约与交互可观测.md` → `R2_RED_EXIT=1`（变更前）。
    - 绿测：`rg -n '^#### R2\\.Q1|^#### R2\\.Q2|^#### R2\\.Q3' ... && rg -n '状态行门控策略|错误分层模型|可观测指标建议' ...` 命中通过。
    - 基线：`PYTHONPATH=src pytest -q ...` → `113 passed, 42 warnings`。
  - Entry:
    - 代码锚点来源：`exec/src/event_processor.rs`、`exec/src/event_processor_with_human_output.rs`、`exec/src/event_processor_with_jsonl_output.rs`、`exec/src/lib.rs`。
- Rollback:
- 回退到 `1a9ee53`（R2 C1）。
- Commits: C1=`1a9ee53`, C2=`6524990`, C3=`TBD`
- Next:
- 进入 R3：先补“商业化契约模板/测试矩阵”文档红测校验命令（C1）。

#### R2.Q1 codex 如何做“状态行门控 + 事件折叠”避免刷屏？
- 状态行门控策略：
  - `BackgroundEvent(agent_job_progress:...)` 被解析为进度模型并单独渲染，普通事件默认不打断进度行。
  - 仅错误/警告/流错误/turn complete/shutdown 等关键事件会中断进度行，保证异常可见性优先。
  - `is_silent_event` 会折叠大批增量型事件（delta、raw item、undo 等），避免冗余输出。
  - `EventProcessor` 生命周期使用 `Running -> InitiateShutdown -> Shutdown`，主循环按状态推进并避免重复关停。
- 代码锚点：
  - `exec/src/event_processor_with_human_output.rs:207-220`
  - `exec/src/event_processor_with_human_output.rs:893-942`
  - `exec/src/event_processor_with_human_output.rs:962-1025`
  - `exec/src/event_processor.rs:7-11`
  - `exec/src/lib.rs:633-643`

#### R2.Q2 错误提示在 codex 中如何分层，nano 可如何映射？
- 错误分层模型：
  - `input` 层：参数/输入问题（无 prompt、stdin 解码失败、schema 文件不可读/非 JSON）直接给出可执行提示并退出。
  - `network/stream` 层：`StreamError` 保留 `additional_details` 拼接后输出，强调传输/上游异常上下文。
  - `runtime` 层：`ErrorEvent` 与 required MCP startup failed 触发 `error_seen` 和主动 shutdown，保证退出码非零。
  - `warning/deprecation` 作为非致命层，允许继续执行但需保留语义标签。
- 代码锚点：
  - `exec/src/lib.rs:757-780`
  - `exec/src/lib.rs:856-890`
  - `exec/src/event_processor_with_human_output.rs:222-241`
  - `exec/src/event_processor_with_human_output.rs:285-295`
  - `exec/src/lib.rs:612-624`
  - `exec/src/lib.rs:646-648`

#### R2.Q3 哪些观测点最能支撑“去重/孤儿事件/工具时间线”？
- 可观测指标建议：
  - `dedup_dropped_total{reason}`：统计被折叠或忽略事件数量。
  - 采样位点A：`is_silent_event` 命中（静默折叠）。
  - 采样位点B：`progress_active && !should_interrupt_progress` 直接 continue（进度期间折叠）。
  - 采样位点C：重复 begin 被跳过（如 web_search begin 去重）。
  - `orphan_total{tool,phase}`：end 到达但没有 begin 配对。
  - 采样位点D：`ExecCommandEnd` 无 begin（当前直接 warn+skip）。
  - 采样位点E：`McpToolCallEnd/CollabEnd` 无 begin（当前 synthesize 新 item）。
  - `tool_timeline_duration_ms{tool,status}`：begin/end 配对得到的耗时分布与失败率。
  - 采样位点F：exec/mcp/collab end 的 `duration` 或状态收口处。
- 代码锚点：
  - `exec/src/event_processor_with_human_output.rs:215-217`
  - `exec/src/event_processor_with_human_output.rs:893-930`
  - `exec/src/event_processor_with_jsonl_output.rs:212-214`
  - `exec/src/event_processor_with_jsonl_output.rs:676-688`
  - `exec/src/event_processor_with_jsonl_output.rs:372-383`
  - `exec/src/event_processor_with_jsonl_output.rs:605-614`
  - `exec/src/event_processor_with_human_output.rs:368-389`
  - `exec/src/event_processor_with_human_output.rs:404-414`

### R3 商业化前契约模板 + M52/M53/M54 测试矩阵草案
- Context:
- M52/M53/M54 需要统一消费同一份“发布前契约”，避免各里程碑分别解释 stdout/stderr、事件折叠、错误层级与指标语义。
- Decision:
- 产出 `商业化前契约模板`（v0.1）和 `测试矩阵草案`（按 M52/M53/M54 映射）。
- 将可复用规则精炼写入 `LOGBOOK.md`，仅保留可执行预防条款。
- Rationale:
- 研究结论只有被模板化、矩阵化后，才能转为可执行验收与跨人协作基线。
- Evidence:
  - Tests:
    - 红测：`rg -n '^#### R3\\.Q1|^#### R3\\.Q2|^#### R3\\.Q3' PROGRESS/M62-Codex-CLI研究三期-TTY非TTY契约与交互可观测.md` → `R3_RED_EXIT=1`（变更前）。
  - Entry:
    - 代码锚点补充：`exec/src/exec_events.rs`（JSON 事件域模型）、`exec/src/event_processor_with_jsonl_output.rs`（事件聚合与容错）。
- Rollback:
- 回退到 `7508dd3`（R3 C1）。
- Commits: C1=`7508dd3`, C2=`TBD`, C3=`TBD`
- Next:
- 运行 R3 校验 + baseline，然后完成 C2/C3 与主干集成。

#### R3.Q1 如何把 R1/R2 的研究结果固化为商业化前契约模板？
- 商业化前契约模板（v0.1）：
  - A. 模式与输出通道契约  
    - `interactive/human`：过程事件与状态行仅 `stderr`；`stdout` 仅 final output。  
    - `jsonl`：`stdout` 仅结构化事件 JSONL；禁止任何非 JSON 文案。  
    - 参考锚点：`exec/src/lib.rs:1-5`, `342-350`, `exec/src/event_processor_with_jsonl_output.rs:846-853`, `.../event_processor_with_human_output.rs:862-883`。
  - B. 状态行与事件折叠契约  
    - 静默事件白名单折叠；仅关键中断事件（error/warning/stream/turn.complete/shutdown）可打断状态行。  
    - 参考锚点：`.../event_processor_with_human_output.rs:893-942`, `962-1025`。
  - C. 错误分层契约  
    - `input`（参数/输入/解码）、`network`（stream transport）、`runtime`（执行失败/依赖失效）三层必须显式标识。  
    - 参考锚点：`exec/src/lib.rs:856-890`, `612-624`, `646-648`。
  - D. 观测契约  
    - 最小必选指标：`dedup_dropped_total`, `orphan_total`, `tool_timeline_duration_ms`。  
    - 参考锚点：`.../event_processor_with_jsonl_output.rs:372-383`, `605-614`, `676-688`。

#### R3.Q2 M52/M53/M54 的测试矩阵草案如何拆？
- 测试矩阵草案：

| Milestone | 主目标 | unit | contract | integration | e2e | 关键断言 | 主要风险 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M52 | TTY/non-TTY 与输出契约落地 | `normalize_output_mode` 判定 | stdout/stderr JSON 契约 | CLI 入口 `isatty` + `--prompt -` | 非 TTY 管道实跑 | stdout 不被过程文案污染 | JSON 污染导致自动化解析失败 |
| M53 | 状态行/折叠/错误分层 | 折叠门控与中断白名单 | Error envelope `layer/code/suggestion` | run-loop 中 begin/end 配对 | managed REPL 长会话 | 错误分层稳定、状态行不刷屏 | 关键事件被误折叠 |
| M54 | 可观测与发布门禁 | 指标计数器与标签映射 | metrics schema 固化 | 事件采样与聚合链路 | 发布前 smoke + 统计校验 | 指标可追溯到具体事件位点 | 只看日志不看指标导致漏判 |

- 分层入口约束：
  - unit 覆盖纯逻辑，不依赖 I/O。
  - contract 固化字段/类型/必填与错误层级。
  - integration 覆盖 CLI 真入口（stdin/stderr、队列模式、run 过滤）。
  - e2e 覆盖 managed 场景长链路（含异常与恢复）。

#### R3.Q3 M52/M53/M54 执行前的发布闸门应如何定义？
- 发布闸门（建议）：
  - Gate-1：`stdout` 契约快照通过（human/json/send-message 三模式）。
  - Gate-2：状态折叠回归通过（重复/孤儿/中断三场景）。
  - Gate-3：错误分层契约通过（input/network/runtime）。
  - Gate-4：指标最小集可采样且与日志可互证。
- 执行顺序建议：
  - 先 M52（通道边界）再 M53（可读性与错误语义）再 M54（观测与发布守门）。
  - 若 Gate-1 失败，后续里程碑不应继续推进。
