# M39 - Codex CLI交互与界面对标研究（续跑记录）

## Baseline
- Test command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py`
- Result:
  - `67 passed, 34 warnings`

---

### R1 Codex CLI交互机制与界面元素清单
- Context:
  - 目标是给出“输入机制 + 运行态反馈 + 并发交互能力”的可定位实现证据，避免停留在主观体验描述。
  - 不改 codex 代码，仅做实现侧盘点。
- Decision:
  - 采用“入口层 + TUI 主循环 + ChatWidget/BottomPane 组件 + 非交互 exec 契约”四层证据链。
  - 直接输出界面元素清单，并附关键代码定位。
- Rationale:
  - 该分层可同时覆盖交互和非交互路径，且能直接映射到 nano CLI 可改造点。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py`
  - Entry: 基线门禁全绿，研究期未改业务代码。
  - 输入机制关键定位:
    - 入口分流（默认交互，`exec` 非交互）：`codex-rs/cli/src/main.rs:55`, `codex-rs/cli/src/main.rs:84`, `codex-rs/cli/src/main.rs:565`, `codex-rs/cli/src/main.rs:574`
    - 交互参数面（prompt/image/model/sandbox/approval/no-alt-screen）：`codex-rs/tui/src/cli.rs:10`, `codex-rs/tui/src/cli.rs:15`, `codex-rs/tui/src/cli.rs:70`, `codex-rs/tui/src/cli.rs:75`, `codex-rs/tui/src/cli.rs:105`
    - Slash 命令体系与可用性约束：`codex-rs/tui/src/slash_command.rs:12`, `codex-rs/tui/src/slash_command.rs:64`, `codex-rs/tui/src/slash_command.rs:127`
    - 输入控件（Enter 提交 / Tab 队列 / 历史导航）：`codex-rs/tui/src/bottom_pane/chat_composer.rs:2342`, `codex-rs/tui/src/bottom_pane/chat_composer.rs:2410`, `codex-rs/tui/src/bottom_pane/chat_composer.rs:2720`, `codex-rs/tui/src/bottom_pane/chat_composer.rs:2701`
    - Popup 同步（命令/文件/mention）：`codex-rs/tui/src/bottom_pane/chat_composer.rs:3176`, `codex-rs/tui/src/bottom_pane/chat_composer.rs:3200`, `codex-rs/tui/src/bottom_pane/command_popup.rs:86`
  - 运行态反馈关键定位:
    - 状态行（spinner+耗时+Esc 中断）：`codex-rs/tui/src/status_indicator_widget.rs:43`, `codex-rs/tui/src/status_indicator_widget.rs:100`, `codex-rs/tui/src/status_indicator_widget.rs:260`
    - 任务态控制与状态显隐：`codex-rs/tui/src/bottom_pane/mod.rs:666`, `codex-rs/tui/src/bottom_pane/mod.rs:673`, `codex-rs/tui/src/bottom_pane/mod.rs:687`
    - 审批弹层与 request_user_input 覆层：`codex-rs/tui/src/bottom_pane/mod.rs:835`, `codex-rs/tui/src/bottom_pane/mod.rs:855`, `codex-rs/tui/src/bottom_pane/request_user_input/mod.rs:121`, `codex-rs/tui/src/bottom_pane/request_user_input/mod.rs:146`
    - 统一执行态摘要/排队消息/待审批线程提示：`codex-rs/tui/src/bottom_pane/unified_exec_footer.rs:45`, `codex-rs/tui/src/bottom_pane/queued_user_messages.rs:13`, `codex-rs/tui/src/bottom_pane/pending_thread_approvals.rs:11`
  - 并发交互能力关键定位:
    - UI 主循环并发选择（app event / active thread event / tui event / thread created）：`codex-rs/tui/src/app.rs:1581`, `codex-rs/tui/src/app.rs:1582`, `codex-rs/tui/src/app.rs:1591`, `codex-rs/tui/src/app.rs:1602`, `codex-rs/tui/src/app.rs:1606`
    - 输入排队与逐条出队：`codex-rs/tui/src/chatwidget.rs:3959`, `codex-rs/tui/src/chatwidget.rs:4617`
    - 运行中编辑最近排队消息：`codex-rs/tui/src/chatwidget.rs:3302`
    - 中断与退出状态机：`codex-rs/tui/src/chatwidget.rs:7143`
    - 多线程/协作代理事件：`codex-rs/tui/src/multi_agents.rs:25`, `codex-rs/tui/src/chatwidget/agent.rs:18`
  - 非交互契约关键定位:
    - stdout/stderr 约束：`codex-rs/exec/src/lib.rs:1`
    - `--json` JSONL 输出：`codex-rs/exec/src/cli.rs:93`, `codex-rs/exec/src/event_processor_with_jsonl_output.rs:847`
    - 默认模式仅最终消息写 stdout：`codex-rs/exec/src/event_processor_with_human_output.rs:862`
- Rollback:
  - 当前为研究文档里程碑，无行为改动；可回退到本 Milestone 开始提交点。
- Commits:
  - C1=`N/A（研究里程碑，无新增测试代码）`, C2=`N/A（研究里程碑，无业务实现）`, C3=`待本次文档提交`
- Next:
  - 输出 nano 对照矩阵并给出 M40 可执行清单。

#### Codex 界面元素清单（聚焦 CLI/TUI）
| 元素 | 作用 | 关键定位 |
| --- | --- | --- |
| Chat Composer | 文本输入、历史回填、Tab 队列提交、弹窗触发 | `codex-rs/tui/src/bottom_pane/chat_composer.rs:2342`, `codex-rs/tui/src/bottom_pane/chat_composer.rs:2720` |
| Command Popup | `/` 命令筛选、补全、选择 | `codex-rs/tui/src/bottom_pane/command_popup.rs:30`, `codex-rs/tui/src/bottom_pane/command_popup.rs:86` |
| File/Mention Popup | `@` 文件检索、技能/App mention | `codex-rs/tui/src/bottom_pane/chat_composer.rs:3225`, `codex-rs/tui/src/bottom_pane/chat_composer.rs:3214` |
| Status Indicator | 运行中 spinner、耗时、中断提示 | `codex-rs/tui/src/status_indicator_widget.rs:43`, `codex-rs/tui/src/status_indicator_widget.rs:260` |
| Approval Overlay | 命令/补丁审批交互 | `codex-rs/tui/src/bottom_pane/mod.rs:835` |
| Request User Input Overlay | 多问题选项+备注+提交 | `codex-rs/tui/src/bottom_pane/request_user_input/mod.rs:121` |
| Queued User Messages | 展示运行中待发送队列，支持取回编辑 | `codex-rs/tui/src/bottom_pane/queued_user_messages.rs:13`, `codex-rs/tui/src/chatwidget.rs:3302` |
| Pending Thread Approvals | 展示其它线程待审批项 | `codex-rs/tui/src/bottom_pane/pending_thread_approvals.rs:11` |
| Unified Exec Footer | 背景终端会话摘要（`/ps`/`/clean`） | `codex-rs/tui/src/bottom_pane/unified_exec_footer.rs:45` |
| Transcript/History Cells | 统一渲染工具调用、补丁、告警、计划更新等 | `codex-rs/tui/src/history_cell.rs:1` |

---

### R2 nano CLI 与 Codex 差距矩阵
- Context:
  - 需要把“当前 nano CLI 能力”与 Codex 对齐到同一维度并形成可执行差距项。
  - 必须覆盖信息密度、可读性、运行态可交互性、错误展示、非交互契约。
- Decision:
  - 以现有 `src/nano_multiagent/cli/**` 与测试契约为基线，形成矩阵并映射到文件级改造点。
- Rationale:
  - 该矩阵可直接驱动 M40 开发任务拆分与测试设计。
- Evidence:
  - nano 关键定位:
    - 单命令模式 stdout 只打印最终 JSON：`src/nano_multiagent/cli/commands.py:121`, `src/nano_multiagent/cli/commands.py:180`
    - 单命令异常也走 JSON 错误对象：`src/nano_multiagent/cli/commands.py:171`
    - REPL 主循环在发送期间阻塞：`src/nano_multiagent/cli/commands.py:252`, `src/nano_multiagent/cli/commands.py:295`
    - async 事件轮询（去重+run_id 过滤+preview）：`src/nano_multiagent/cli/repl_events.py:29`, `src/nano_multiagent/cli/repl_events.py:116`, `src/nano_multiagent/cli/repl_events.py:139`
    - 输入引擎（左右编辑+历史+仅“单个/”菜单）：`src/nano_multiagent/cli/repl_input.py:129`, `src/nano_multiagent/cli/repl_input.py:359`
    - REPL 命令集合：`src/nano_multiagent/cli/repl_commands.py:10`
    - 分层错误输出：`src/nano_multiagent/cli/repl_commands.py:227`, `src/nano_multiagent/cli/error_presenter.py:45`
    - 非交互合同测试（单行 JSON）证据：`tests/integration/test_cli_http_flow_integration.py:246`
- Rollback:
  - 文档改动可直接回退到本里程碑前稳定点。
- Commits:
  - C1=`N/A`, C2=`N/A`, C3=`待本次文档提交`
- Next:
  - 形成 M40 任务清单（优先 CLI-only）。

#### 差距矩阵（Codex vs nano CLI）
| 维度 | Codex 现状 | nano 现状 | 差距结论 | M40 对应改造点 |
| --- | --- | --- | --- | --- |
| 信息密度 | 同屏聚合状态、排队消息、后台终端摘要、审批提示（`status_indicator` + `queued_user_messages` + `unified_exec_footer`） | 事件 preview 逐行打印，信息分散在多行日志与 JSON（`repl_events.py`） | nano 信息组织偏“日志流”，缺乏结构化“状态面板” | CLI-only：新增渲染层与状态模型，按“状态行+队列+工具区”分区输出 |
| 可读性 | 命令弹窗、fuzzy 过滤、补全、上下文提示和多 modal 协同 | slash 菜单仅在“输入仅为 / 且光标=1”时出现；命令发现成本高 | nano 交互可发现性明显低于 Codex | CLI-only：增强 `repl_input.py` 为“前缀触发+筛选+补全”，并统一命令帮助视图 |
| 运行态可交互性 | 运行中可继续输入并排队，支持取回编辑，支持中断与继续推进 | 发送阶段阻塞输入循环；无运行中排队编辑能力 | nano 缺少“边运行边交互”核心能力 | CLI-only：`commands.py` + `repl_events.py` 引入 RunController/队列；`http_client.py` 增加 cancel API 调用 |
| 错误展示 | 交互态区分告警/错误 cell，非交互态区分 stdout/stderr，JSONL 事件可机读 | REPL 有 Layer/Suggestion，但运行态错误主要文本串；事件错误与状态切换耦合 | nano 的错误可定位性中等，运行态可观察性不足 | CLI-only：标准化事件态错误渲染（run/tool/network/input）；收敛错误码到统一视图 |
| 非交互模式契约 | `exec` 明确：默认 stdout 只最终消息，`--json` 为 JSONL，其他输出走 stderr | `commands.py` 保证命令模式单 JSON stdout；集成测试已锁定 | nano 契约已具备，是保留项，不应被 REPL 改造污染 | CLI-only：新增测试守卫“send-message 永不输出事件噪声到 stdout” |

---

### R3 面向 M40 的可执行改造清单（仅 CLI 层）
- Context:
  - 需要可直接交付下一里程碑执行，不做本里程碑实现。
  - 优先 `src/nano_multiagent/cli/**`，并给出必要测试入口。
- Decision:
  - 将任务分为 `CLI-only` 与 `需内核 API 支持` 两组，优先前者。
- Rationale:
  - 避免在 M40 初期因边界不清导致跨层返工。
- Evidence:
  - cancel 端点已存在，可由 CLI 直接利用：`src/nano_multiagent/server/routes/run.py:51`
  - 当前 SSE 事件类型有限（`run_status/tool_start/tool_end/text_delta/turn_end`）：`src/nano_multiagent/runs/registry.py:424`, `src/nano_multiagent/runs/registry.py:451`, `src/nano_multiagent/runs/registry.py:464`, `src/nano_multiagent/runs/registry.py:480`, `src/nano_multiagent/runs/registry.py:491`
- Rollback:
  - 文档类里程碑，无运行时代码回退动作。
- Commits:
  - C1=`N/A`, C2=`N/A`, C3=`待本次文档提交`
- Next:
  - M40 按下列 P0->P1 顺序执行。

#### M40 执行清单（CLI-only，优先）
1. `src/nano_multiagent/cli/http_client.py`
   - 新增 `cancel_run(run_id)` 方法，调用 `POST /v1/runs/{run_id}/cancel`。
   - 为 run polling/取消失败场景补充统一异常类型（含 layer/suggestion 元数据）。
2. `src/nano_multiagent/cli/repl_events.py`
   - 引入 `RunViewState`（status/tool/text/usage）聚合器，替代散乱即时 print。
   - 将 `consume_async_run_events` 重构为“增量归并 + 结构化渲染事件”。
3. `src/nano_multiagent/cli/commands.py`
   - 拆出 REPL 运行控制器（建议新模块 `repl_runtime.py`），使发送与输入解耦。
   - 支持运行中输入排队、最近排队消息取回编辑、Ctrl-C 触发 cancel_run。
   - 保持命令模式 stdout 单 JSON 不变。
4. `src/nano_multiagent/cli/repl_input.py`
   - 将 slash 菜单触发从“仅 /”升级为“前缀触发 + 过滤 + 选中补全”。
   - 增加可配置快捷键映射（至少支持 Tab 队列、Esc 中断提示）。
5. `src/nano_multiagent/cli/repl_commands.py`
   - 与新输入模型对齐命令元数据（描述、可运行态可用性、参数提示）。
6. 建议新增模块（均在 `src/nano_multiagent/cli/`）
   - `repl_models.py`: 运行态视图模型。
   - `repl_render.py`: 统一渲染器（状态行/工具事件/错误区）。
   - `repl_runtime.py`: 发送、轮询、取消、队列调度器。

#### M40 测试清单（建议）
1. Unit
   - `tests/unit/test_cli_repl_runtime.py`：运行中排队、取消、出队顺序。
   - `tests/unit/test_cli_repl_render.py`：状态行与事件分区渲染。
   - `tests/unit/test_cli_repl_input_menu.py`：slash 过滤与补全行为。
2. Integration
   - 扩展 `tests/integration/test_cli_http_flow_integration.py`：
     - 运行中二次输入排队并在首轮完成后自动发送。
     - Ctrl-C 触发 `cancel_run` 并输出可行动建议。
3. Contract
   - 扩展 `tests/contract/test_cli_http_only_contract.py`：
     - `send-message` 在 async-capable client 下仍保持 stdout 单 JSON。
     - REPL 事件输出不污染单命令模式。

#### 需要内核 API 支持（记录，不实施）
1. 审批/问答交互覆层对齐 Codex
   - 需新增事件类型（如 `approval_request`、`request_user_input`）及对应回传接口。
   - 现有事件模型不支持这类双向交互（仅状态/工具/文本）。
2. 多线程协作与跨线程待审批视图
   - 需内核提供“thread 级事件与状态聚合”能力；当前 run 维度 API 无线程协作语义。
3. 更细粒度运行过程可视化
   - 若要对齐 Codex 的 exec 过程分段显示，需内核输出更细粒度命令执行事件（begin/chunk/end 细分与可关联 ID）。
