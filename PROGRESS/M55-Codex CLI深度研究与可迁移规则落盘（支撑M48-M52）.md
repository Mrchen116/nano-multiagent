# M55 Codex CLI深度研究与可迁移规则落盘（支撑M48-M52）

日期：2026-03-04  
分支：`milestone/M55`  
工作区：`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55`

### R1 输入状态机/渲染调度锚点补齐
- Context:
  - M55 目标要求补齐 4 类研究锚点：`popup同步`、`frame coalesce`、`orphan处理`、`fallback去重窗口`。
  - 范围仅文档落盘，不能触碰 `src/nano_multiagent/core|server|agent|runs|tools/**`。
- Decision:
  - 以“Codex源码锚点 + nano现状落点 + 迁移规则”三列方式固化证据。
  - 统一把 M48-M52 直接可执行落点绑定到 `src/nano_multiagent/cli/**`。
- Rationale:
  - 仅列结论容易失真；绑定行号锚点可让后续里程碑直接复核与执行。
- Evidence:
  - Tests: `N/A（research-only）`
  - Entry: 四类主题均给出 Codex 与 nano 的可检索锚点。

#### 锚点矩阵（补齐项）
| 主题 | Codex 代码锚点 | nano 迁移落点 | 可迁移规则 |
| --- | --- | --- | --- |
| popup 同步状态机 | `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/bottom_pane/chat_composer.rs:1227`（按键入口统一分发）; `.../chat_composer.rs:1277`（每次按键后 `sync_popups()`）; `.../chat_composer.rs:3176`（popup 收口）；`.../chat_composer.rs:3188`（历史导航期间强制关闭 popup） | `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/src/nano_multiagent/cli/repl_input.py:155`; `.../repl_input.py:332`; `.../repl_input.py:476` | 输入处理后必须统一走一次 popup 同步函数，不能在分支内多点开关菜单；历史回填时禁用 popup 抢焦点。 |
| frame coalesce + 调度 | `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/tui/frame_requester.rs:6`（coalesce 设计）; `.../frame_requester.rs:96`（调度循环）；`.../frame_requester.rs:111`（最早 deadline 合并）；`.../frame_requester.rs:113`（禁止请求时立即 redraw）；`.../streaming/commit_tick.rs:69`（commit tick）；`.../commit_tick.rs:82`（CatchUpOnly gate） | `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/src/nano_multiagent/cli/repl_input.py:365`; `.../repl_input.py:384`; `.../repl_input.py:416` | redraw 请求与真正渲染要解耦，合并成“最早一帧”触发；高频输入/事件不应每条直接重绘。 |
| orphan 事件处理 | `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:2436`（`handle_exec_end_now`）；`.../chatwidget.rs:2466`（active 组内不含 call_id 判定 orphan）；`.../chatwidget.rs:2507`（OrphanHistoryWhileActiveExec 分支）；`.../exec_cell/model.rs:77`（`complete_call` 返回 bool，错配显式暴露） | `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/src/nano_multiagent/cli/repl_events.py:233`; `.../repl_events.py:261`; `.../repl_events.py:285` | `tool_exec_exit` 遇到未知/错配 call_id 时不能并入当前活动组，需落单独 orphan 条目并计数。 |
| fallback 去重窗口锚点 | `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:2644`（wait 交互去重抑制）；`.../chatwidget.rs:2655`（按 call_id 抑制重复发射）；`.../chatwidget/realtime.rs:80`（realtime user message 去重） | `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/src/nano_multiagent/cli/repl_events.py:37`; `.../repl_events.py:159`; `.../repl_events.py:486`; `.../repl_events.py:519`; `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/src/nano_multiagent/cli/http_client.py:330` | event_id 缺失时必须进入 fallback key，但 key 存储需改为按 run_id 分桶的 TTL/LRU 窗口；不能无界 set 增长。 |

- Rollback:
  - 研究文档可回退到本里程碑首个落盘提交。
- Commits: C1=`N/A`, C2=`N/A`, C3=`TBD`
- Next:
  - 按 M48-M52 拆分执行清单并绑定具体文件入口。

### R2 可执行迁移清单（M48-M52 分配）
- Context:
  - 需要把 R1 的研究证据转成后续里程碑可直接执行的拆分清单。
  - 依赖关系以 M47 DAG 为准：`M48/M49` 并行，`M50 <- M49`，`M51 <- M49+M50`，`M52 <- M48+M50`。
- Decision:
  - 为每个里程碑给出：目标、落点文件、执行项、主要风险/防回归。
- Rationale:
  - 保证后续实现里程碑不再重复做“研究-映射”动作，直接开工即可。
- Evidence:
  - Tests: `N/A（research-only）`
  - Entry: 清单按 M48-M52 分项，可直接转为实现 Roadpoint。

#### M48（输入状态机 + popup 同步）
- 目标：把输入编辑、历史回填、slash 菜单收敛为单状态机，并显式输出 `needs_redraw`。
- 落点文件：
  - `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/src/nano_multiagent/cli/repl_input.py`
  - `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/tests/unit/test_cli_main.py`
- 执行项：
  - 抽出统一 `sync_popups()`（或等价函数），替换当前每个分支里重复调用 `_sync_command_menu_selection` 的模式。
  - 历史导航态 (`history_index is not None`) 强制关闭 slash popup，防止菜单抢焦点。
  - `Esc` 只关闭 popup，不改输入内容；补对应交互测试。
- 风险/防回归：
  - 风险：回填历史时菜单与输入错位。
  - 防回归：新增“历史浏览期间 popup 必为空”测试。

#### M49（事件归一化 + fallback 去重窗口）
- 目标：把事件去重从“event_id 优先 + 无界 fallback set”升级为“语义键 + 分桶窗口”。
- 落点文件：
  - `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/src/nano_multiagent/cli/repl_events.py`
  - `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/src/nano_multiagent/cli/http_client.py`
  - `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/tests/unit/test_cli_main.py`
- 执行项：
  - 在 `consume_async_run_events` 中引入按 `run_id` 分桶的 fallback dedupe window（TTL + 上限）。
  - `_event_replay_dedupe_key` 去掉非语义字段（如 `ts`）影响，保持 `name/call_id/phase/seq` 优先。
  - 为 `event_id==""` 场景补“窗口命中/过期/溢出”测试，避免 replay 污染。
- 风险/防回归：
  - 风险：key 太粗吞真实事件，太细放过重放。
  - 防回归：按事件类型分键，且测试覆盖 changed-event-id + nonsemantic metadata。

#### M50（渲染调度 + 阶段状态机）
- 目标：建立 `STREAMING -> FINALIZING -> FINALIZED` 阶段门控，并引入合帧调度。
- 落点文件：
  - `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/src/nano_multiagent/cli/repl_input.py`
  - `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/src/nano_multiagent/cli/repl_render.py`
  - `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/src/nano_multiagent/cli/commands.py`
- 执行项：
  - 渲染入口拆分为“请求重绘”和“执行重绘”两层，输入与事件仅发请求。
  - 阶段进入 `FINALIZING` 后禁止再发 preview，防止 preview/final 双播。
  - `emit_external_text` 保留光标恢复语义，但重绘触发改为调度器统一执行。
- 风险/防回归：
  - 风险：状态线恢复时机错误导致重复“进行中”提示。
  - 防回归：新增阶段转换与状态线恢复时序测试。

#### M51（工具时间线聚合 + orphan 隔离）
- 目标：把工具事件聚合从“按 group_key 覆盖字段”升级为“active timeline + orphan 支路”。
- 落点文件：
  - `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/src/nano_multiagent/cli/repl_events.py`
  - `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/src/nano_multiagent/cli/repl_render.py`
  - `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/tests/unit/test_cli_main.py`
- 执行项：
  - `tool_exec_exit` 在未命中 active `call_id` 时生成 orphan timeline 项而非覆盖当前组。
  - 为 orphan 输出单独文案与指标（如 `orphan_events`），避免“吞尾事件”。
  - 保持 `tool_start/tool_exec_started/tool_exec_exit` preview 幂等身份键一致。
- 风险/防回归：
  - 风险：跨工具串味，结束事件覆盖错误组。
  - 防回归：新增“active 组 + orphan exit 并存”回归测试。

#### M52（TTY / non-TTY 双通道契约）
- 目标：固化“REPL 人类输出”和“单命令 JSON 输出”双通道，不互相污染。
- 落点文件：
  - `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/src/nano_multiagent/cli/commands.py`
  - `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/src/nano_multiagent/cli/repl_input.py`
  - `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55/tests/unit/test_cli_main.py`
- 执行项：
  - 明确 `send-message` 路径永远单 JSON stdout；REPL preview/summary 仅走交互通道。
  - 非 TTY 场景禁用交互渲染副作用，保持脚本可机读。
  - 对 run queue draining 与退出路径补充契约测试，避免退出时残留半行输出。
- 风险/防回归：
  - 风险：交互事件污染脚本 JSON。
  - 防回归：新增 non-interactive stdout 精确断言（仅 1 行 JSON）。

- Rollback:
  - 回退到迁移清单落盘前版本即可。
- Commits: C1=`N/A`, C2=`N/A`, C3=`TBD`
- Next:
  - 在 LOGBOOK 追加跨里程碑可复用规则，供 M48-M52 执行直接引用。

### R3 研究结论沉淀与复用规则更新
- Context:
  - 需要把研究结果沉淀为“可复用防回归规则”，避免后续执行时再次走偏。
- Decision:
  - 将四类规则（popup、coalesce、orphan、fallback window）追加到 `LOGBOOK.md`。
  - 将 M55 的交付摘要与执行边界写入本 PROGRESS，作为主 agent 验收依据。
- Rationale:
  - LOGBOOK 只保留可复用规则，PROGRESS 保留里程碑内决策与证据，职责分离更稳定。
- Evidence:
  - Tests: `N/A（research-only）`
  - Entry: `PROGRESS/M55...` 与 `LOGBOOK.md` 同步更新。
- Rollback:
  - 回退到本次 docs 提交前 commit。
- Commits: C1=`N/A`, C2=`N/A`, C3=`TBD`
- Next:
  - 提交并合并 main，随后更新 `data/dev-tasks.json` 的 M55 状态为 `DONE`。
