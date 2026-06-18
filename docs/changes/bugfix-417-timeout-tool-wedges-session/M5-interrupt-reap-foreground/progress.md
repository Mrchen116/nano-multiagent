# bugfix-417-M5: interrupt-reap-foreground — Progress

> 已知项 #114 纳入本 unit。对齐 ../design.md 决策 10 +「B 升级：中断收尾」+ Changelog 顶部 M5 细化 + delta-spec(kernel/gateway/im)。
> 状态：**DONE**（代码 + 单测 + e2e DONE 闸 + 双产品 live + IM 卡真浏览器取证全过）。

## 缺陷与总修法（一句话）

`/stop`(kernel.interrupt) / `kernel.cancel` 只释放会话锁（Req A 已 pass），但不杀正在跑的前台
bash 子进程（留孤儿）、不收口在飞 tool_call 徽标（停 running）。根因：interrupt 是 cooperative
abort，前台 bash 的 `to_thread` 阻塞在 `completed_event.wait(budget)`，子进程不死则永不返回 →
锁在外层、子进程在内层，必须主动 kill 内层。修法：经注入 `ForegroundStopper` 端口定位该 session
在飞前台工具 → killpg 整树 + 立即唤醒 waiter → run 解开 → 既有 `_recover_orphaned_tool_calls`
收口「已中断」；用户主动中断回填 CC 原串、IM 卡用户可见。

## Roadpoint 结构化记录

### R1 — 红测（interrupt/cancel 收前台子进程 + 收口徽标 + 退化 + 端口注入）

- **Context**：缺口是 interrupt 不触发在飞前台工具 stopper；需先红测钉住「杀子进程树 + 收口
  徽标 + 无在飞工具时退化纯 abort + core 不依赖 platform」。
- **Decision**：在 `test_run_cancel.py` / `test_background_tasks.py` / 真实 build_kernel
  集成测试写红测，注入 fake `ForegroundStopper` 记录调用。
- **Rationale**：先固化对外可观察契约再实现，避免实现牵着测试走。
- **Evidence**：红测初始失败（缺 `foreground_stopper` 形参 / 缺 `stop_foreground_for_session`），
  实现后转绿。
- **Rollback**：删红测文件即回退（不影响生产）。
- **Commits**：`0f3c9d93` test。

### R2 — stop_foreground_for_session + interrupt/cancel 前台收尾 + kernel 注入

- **Context**：定位「在飞前台工具」需把前台 blocking 任务与用户显式 `run_background` 区分开。
- **Decision**：`BackgroundTaskRegistry` 加 `foreground` 标记 + `stop_foreground_for_session(session_id)`
  （按 session 只对 `foreground=True` 的 stop_handle killpg，放过后台任务、忽略终态、按 session 作用域）；
  前台 bash `set_stop_handle(foreground=True)`（auto-background 时降级 `False`）；`RunsRegistry`
  注入 `ForegroundStopper` 协议端口，interrupt 有在飞前台工具时杀树 + 置 CANCELLED + force-cancel，
  无则退化纯 abort，cancel 也杀树；kernel build 后 `set_foreground_stopper` 接 BackgroundTaskRegistry。
- **Rationale**：复用既有 `set_stop_handle`/killpg/`_recover_orphaned_tool_calls`；core 只调协议
  方法、永不 import platform（决策 10 硬约束）。interrupt force-cancel 后须先置 CANCELLED——raw
  CancelledError 出 `_run_worker_async` 不命中 `except Exception` 终态标记（同 M1 cancel）。无在飞
  前台工具时不 force-cancel，保 `test_interrupt_signals_active_run_to_abort` 的 `stop_reason=aborted`
  不回归（决策 10「只在确有在飞前台工具时触发」）。
- **Evidence**：`stop_foreground_for_session` 四例（只杀前台/按 session/忽略终态/无任务返回 False）；
  interrupt force-cancel 释锁、退化 abort、cancel 杀树单测绿。
- **Rollback**：M5 可独立 revert，退回「释放锁但留子进程」（pre-existing，不更坏）。
- **Commits**：`889be506` fix。

### R3 — 前台中断不滞留线程（team-lead 强调的 subtlety）

- **Context**：M4 `_stopped` 静默路径**不** set `completed_event`（为后台 task_stop 设计、无前台
  waiter）。前台 `_run_foreground` 阻塞在 `completed_event.wait(budget)`——只 force-cancel run 协程
  会让该 to_thread 工作线程卡到 120s budget 才退（线程泄漏）。
- **Decision**：前台登记 `_ForegroundStopper` 包装器，`stop()` 在 `stopper.stop()`（killpg 整树）后
  **立即** `result_holder["status"]="interrupted"` + `completed_event.set()` → `_run_foreground`
  即时返回 benign interrupted 结果（exitCode 130），不滞留。
- **Rationale**：在产品层（bash.py）最小增量解决，不改 ShellRunner 的 `_stopped` 语义（那为后台
  task_stop 服务）。
- **Evidence**：窄单测——「永不自完成」runner，/stop 后 `tool.run` 在 <5s 返回（budget 设 30s）+
  killpg 被调 + result interrupted。live 实测中断后 **~1.1s** 子进程死（非 120s）。
- **Rollback**：移除包装器回退到滞留行为（pre-existing，不更坏）。
- **Commits**：`b03de323` fix（与 R4 同 commit）。

### R4 — content 按中断来源解耦（决策 10 / Changelog）

- **Context**：用户主动中断（/stop、CLI Ctrl-C）回填的 tool result content 须与 CC 完全一致
  `[Request interrupted by user for tool use]`（模型熟悉、知道用户主动停）；watchdog/崩溃的系统
  中断仍 `[interrupted]`，不冒用「用户」归因。badge 两者都「已中断」。
- **Decision**：`RunController.abort(user_initiated=)` + `is_user_interrupt`；`registry.interrupt`
  标 user_initiated → runtime `_recover_orphaned_tool_calls` 透传 → `append_tool_call_recovery(content=)`
  → jsonl 合成优先 `content`（fallback `[{reason}]`）。常量 `USER_INTERRUPT_RECOVERY_CONTENT`
  在 `jsonl_store.py` 定义、经 `agent.sdk` 再导出（单一来源）。
- **Rationale**：content 与 badge reason 解耦——reason 恒 `interrupted`（badge=已中断），仅 content
  按来源给文本，satisfies「同一份 content 供模型 transcript + IM 卡两面」。
- **Evidence**：单测两路——user → CC 串、system（无 content）→ `[interrupted]`，`recovery_reason`
  都 `interrupted`。
- **Rollback**：interrupt 不标 user_initiated 即退回统一 `[interrupted]`（pre-existing 语义）。
- **Commits**：`b03de323` fix。

### R5 — IM 工具卡显示用户中断 content（gateway reconcile → output）

- **Context**：模型侧 content 已满足，但**用户可见的 IM 卡**走 gateway `run_terminal_reconcile`
  → `main.py` 投影成 `tool_call_completed`，原只带 name/status/reason/input，**不带 content** →
  卡上看不到 CC 串。
- **Decision**：gateway `/stop` 标记 `_user_interrupted_runs`；`_emit_terminal_reconcile` 对其在
  reconcile 事件带 `content`（取 sdk 再导出的常量）→ `main.py` 投影成在飞 tool_call 的 `output`；
  系统收尸不带 content。前端 `ToolCallRow` 既有渲染（`collapsedSummary(call.output)` 渲染返回内容、
  `REASON_LABEL_KEYS[interrupted]` 渲染「已中断」badge）——**无需改 frontend**。
- **Rationale**：复用既有 `tool_call.output` 渲染链，不新增 UI 组件；content 单一来源经 sdk。
- **Evidence**：observer 两路单测（user-interrupted run → output=CC 串；系统收尸 → 无 output）+
  gateway `_emit_terminal_reconcile` 单测；**真浏览器取证**见 §「IM 卡用户可见取证」。
- **Rollback**：reconcile 不带 content 即退回「卡只有 badge 无返回内容」（pre-existing）。
- **Commits**：`9c02e370` feat。

### R6 — CLI Ctrl-C → kernel.interrupt（asyncio signal handler + REPL 存活）

- **Context**：coding_cli 原无 Ctrl-C → interrupt 接线，turn 中 Ctrl-C 直接掀进程（留孤儿）。
  design M5 行 [reviewer]「CLI Ctrl-C 同走 interrupt」+ Runbook CLI 旅程要求与 CC 一致。
- **Decision**：`commands.py` turn 流式循环 in-loop `except KeyboardInterrupt` 作兜底 +
  `loop.add_signal_handler(SIGINT)`——turn 活跃时 `kernel.interrupt`（用户发起 stop 路径，杀前台
  子进程树 + 收口徽标 + 回填 CC 串），idle 时 `raise KeyboardInterrupt` 退回默认退出；interrupted
  run 返回 benign payload → **CLI 留在 REPL 不掀进程**，可继续敲下一句。退出 `remove_signal_handler`。
- **Rationale**：**live 暴露关键**——`asyncio.run` 下 SIGINT 在 loop 层抛 KeyboardInterrupt，**不
  落进** per-turn 的 `async for`，仅靠 stream 循环里的 `except` 捕不到 → 必须 signal handler。
  无 `add_signal_handler` 的平台（Windows）/测试 harness 退回 in-loop except 兜底。
- **Evidence**：CLI 单测（Ctrl-C → kernel.interrupt + REPL 存活、不报 send failed）；CLI live
  取证见 §「双产品 live」。
- **Rollback**：移除 signal handler 回退到「Ctrl-C 掀进程」（pre-existing，不更坏）。
- **Commits**：`9c02e370` feat（in-loop）+ `26a4bceb` fix（signal handler）。

### R7 — build_kernel 端到端 DONE 硬闸

- **Context**：interrupt→reap→recover→self-heal 跨 kernel.interrupt→registry→stopper→bash
  to_thread→runtime finally→JSONL recovery 多层，孤立单测覆盖不到这条缝。
- **Decision**：`tests/integration/test_bugfix_417_interrupt_reap_e2e.py` 经真实 `build_kernel`
  wiring（fake model client，不挂 e2e marker）：前台 sleep 被 interrupt → pgrep 无孤儿 + run
  cancelled + JSONL `tool_call_recovery` reason=interrupted & content=CC 串 + 同会话自愈 completed。
- **Rationale**：决策 8 测试策略——DONE 硬闸用自动化端到端替代「只靠人手 live」。拆分到独立文件守
  400 行 cap。
- **Evidence**：3 passed（含 silent-heartbeat / tool_timeout / interrupt-reap）。
- **Rollback**：删测试文件即回退。
- **Commits**：`0f3c9d93` test（建）+ 后续 commit 增 interrupt 用例。

## 全树测试与静态检查（Evidence 汇总）

- 全树 `pytest -m "not e2e"`：**2679 passed, 0 failed, 1 skipped**（skip 为 pre-existing，无关）。
- `ruff check src/ tests/` + `ruff format --check src/ tests/`：clean。
- 端到端 DONE 硬闸（真实 build_kernel）：**3 passed**。
- contract / run_cancel / e2e 复核：**15 passed**（team-lead 侧复核）。
- contract 白名单（行号锚定）随插入位移逐次更新：`test_no_hardcoded_workspace_dirname`
  (kernel.py 469→480、runtime.py 177→180、jsonl_store.py 81→89、commands.py 1146/1147→1232/1233)、
  `test_agent_sdk_surface_guard`（新增 `USER_INTERRUPT_RECOVERY_CONTENT` 两闸）、
  `test_test_naming_and_size_contract`（拆分 interrupt-reap DONE 闸到独立文件守 400 行 cap）。

新增/扩展测试文件：
- `tests/unit/agent/background_tasks/test_background_tasks.py`（stop_foreground_for_session 四例）
- `tests/unit/test_run_cancel.py`（interrupt force-cancel / 退化 abort / cancel 杀树）
- `tests/unit/agent/tools/test_bash_tool.py`（前台 stopper 即时唤醒不滞留线程）
- `tests/unit/test_session_manager.py`（content 解耦 user vs system）
- `tests/unit/test_inbound_pipeline_streaming.py` + `tests/unit/personal_assistant/test_inbound_pipeline_user_interrupt_content.py`（gateway reconcile content 两路）
- `tests/unit/test_cli_async_repl_sdk.py`（CLI Ctrl-C → interrupt + REPL 存活）
- `tests/integration/test_bugfix_417_interrupt_reap_e2e.py`（真实 build_kernel DONE 闸）

## 双产品 live 复验（真 LLM proxy 127.0.0.1:4000）

worktree ephemeral 端口 + worktree config 副本 + `--auto-bind`，自起自 kill，已干净停服清产物。
一次性验收证据（pexpect 驱动 CLI / IM REST 驱动 PA），不入回归套件：

- **CLI**：`python -m coding_cli.main` 跑前台 `sleep <marker>` → Ctrl-C →
  - 子进程 **~1.1s** 死（pgrep 无孤儿，非 120s budget）
  - REPL 自愈：随后 "RECOVERED" 正常回复，**CLI 没退出、能继续敲下一句**
- **PA(IM+Gateway)**：IM 发前台 `sleep <marker>` → `/stop` →
  - 子进程 **~1.1s** 死（pgrep 无孤儿）
  - IM 工具卡返回内容显示 `[Request interrupted by user for tool use]`
  - 在飞工具 badge 收口「已中断」（reason=interrupted）
  - 同会话发新消息正常回复（Req A 不回归）

## IM 卡用户可见取证（真浏览器，team-lead 要求看到真页面）

构建真前端 `dist`（`vite build`；分支上 `tsc -b` 有 pre-existing 类型报错——
`message-pane.test.tsx` style + Pluggable，与本 milestone 零关、本 milestone 不碰 frontend src），
IM serve dist，Playwright(Chromium) 真开浏览器渲染：PA `/stop` 前台 `sleep` 后展开工具卡 + DOM
取证 + 全页截图。

- REST 侧确认持久化 tool_call：`status=failed, reason=interrupted,
  output='[Request interrupted by user for tool use]'`。
- 浏览器 DOM 断言（zh locale）：含 `[Request interrupted by user for tool use]` = True、
  含「已中断」badge = True。
- 截图证据：`ACCEPTANCE/bugfix-417-M5/im-tool-card-interrupted-zh.png`——展开的 `✕ bash`
  工具卡显示返回内容 `[Request interrupted by user for tool use]` + 红色「已中断」badge
  （en locale 下同一处为 "Interrupted"）。

## 范围

派发的 `core/runs/registry.py` `sdk/kernel.py` `core/agent/runtime.py` 外，按 team-lead 批准/要求扩到：
`core/background_tasks/registry.py`、`core/agent/run_control.py`、`core/session/jsonl_store.py` +
`manager.py`、`platform/tools/builtins/bash.py`、`sdk/__init__.py`、
`personal_assistant/gateway/inbound_pipeline.py` + `main.py`、`coding_cli/commands.py`。
均**未碰** M6 的 `core/tools/registry.py` / `core/agent/liveness.py` / `realtime_stream.py`，与 M6 无交集。
frontend src **零改动**（A 用既有 `tool_call.output` 渲染）。

## Commits（milestone/bugfix-417-M5）

| commit | phase | 内容 |
|---|---|---|
| `0f3c9d93` | test | 红测：interrupt/cancel 收前台子进程树 + 收口徽标已中断 |
| `889be506` | fix | interrupt/cancel 杀在飞前台工具子进程树并收口徽标 |
| `b03de323` | fix | 前台中断不滞留线程 + 用户中断回填 CC 归因 content |
| `9c02e370` | feat | 用户中断 content 上 IM 工具卡 + CLI Ctrl-C 接 interrupt（in-loop） |
| `26a4bceb` | fix | CLI Ctrl-C 用 asyncio signal handler 接 interrupt |
| `f2a42714` | docs | tasks.md + progress.md（初版） |
| (本提交) | docs | progress.md 改 per-R 结构化 + IM 卡真浏览器取证截图 |

## 已知项/后续

无遗留。M5 闭环：#114 中断收尾在双产品端到端可用，含用户可见 IM 卡真浏览器取证。
