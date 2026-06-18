# bugfix-417-M5: interrupt-reap-foreground — Progress

> 已知项 #114 纳入本 unit。对齐 ../design.md 决策 10 + 「B 升级：中断收尾」+ Changelog 顶部 M5 细化 + delta-spec(kernel/gateway/im)。

## 状态：DONE

分支 `milestone/bugfix-417-M5`，提交（顶 → 底）：

| commit | phase | 内容 |
|---|---|---|
| `26a4bceb` | fix | CLI Ctrl-C 用 asyncio signal handler 接 interrupt（含 contract 白名单行号修正） |
| `9c02e370` | feat | 用户中断 content 上 IM 工具卡 + CLI Ctrl-C 接 interrupt（in-loop 兜底） |
| `b03de323` | fix | 前台中断不滞留线程 + 用户中断回填 CC 归因 content |
| `889be506` | fix | interrupt/cancel 杀在飞前台工具子进程树并收口徽标 |
| `0f3c9d93` | test | 红测：interrupt/cancel 收前台子进程树 + 收口徽标已中断 |

## 根因与修法

**缺口**：`/stop`(kernel.interrupt) / `kernel.cancel` 只释放会话锁（Req A 已 pass），但
①不杀正在跑的前台 bash 子进程（留孤儿）②不收口在飞 tool_call 徽标（停 running）。
**根因**：interrupt 是 cooperative abort；前台 bash 的 `to_thread` 阻塞在
`completed_event.wait(budget)`，子进程不死则永不返回 → run 不结束 → 锁在外层、子进程在内层，
必须主动 kill 内层。

**修法（复用既有原语，core 不依赖 platform）**：

1. **定位 + 杀树**：`BackgroundTaskRegistry.stop_foreground_for_session(session_id)` 按 session
   只对 `foreground=True` 的 stop_handle 调 `stop()`（M4 已硬化 killpg 整树），放过用户
   `run_background` 的后台任务。前台 bash `set_stop_handle(foreground=True)`（auto-background
   时降级 `foreground=False`）。
2. **端口注入**：`RunsRegistry` 持 `ForegroundStopper` 协议端口（kernel build 后
   `set_foreground_stopper` 接 `BackgroundTaskRegistry.stop_foreground_for_session`）。core
   只调协议方法，永不 import platform。
3. **interrupt 解开 parked run**：有在飞前台工具时杀树 → 置 CANCELLED 终态 → force-cancel 承载
   Task（raw CancelledError 出 `_run_worker_async`，不命中 `except Exception` 终态标记，故须先置态，
   同 M1 cancel）；无在飞前台工具时退化纯 abort（`stop_reason=aborted` 不回归）。cancel 也杀树。
4. **线程不滞留（team-lead 强调的 subtlety）**：M4 `_stopped` 静默路径不 set completed_event
   （为后台 task_stop 设计、无前台 waiter）。前台登记 `_ForegroundStopper` 包装器，`stop()` 在
   killpg 后**立即** set `completed_event` → `_run_foreground` 即时返回 interrupted（exitCode 130），
   不卡 120s budget。live 实测中断后 **~1.1s** 子进程死。
5. **content 按来源解耦（决策 10 / Changelog）**：`RunController.abort(user_initiated=)` +
   `is_user_interrupt`；interrupt 标 user_initiated → runtime `_recover_orphaned_tool_calls`
   透传 → `append_tool_call_recovery(content=)` → jsonl 合成优先 `content`（fallback
   `[{reason}]`）。用户中断回填 CC 原串 `[Request interrupted by user for tool use]`；系统中断
   （watchdog/崩溃）仍 `[interrupted]`。badge 都「已中断」（recovery_reason 不变）。常量
   `USER_INTERRUPT_RECOVERY_CONTENT` 经 `agent.sdk` 再导出（单一来源）。
6. **IM 工具卡 content**：gateway `/stop` 标记 `_user_interrupted_runs`，`_emit_terminal_reconcile`
   对其在 reconcile 事件带 `content` → `main.py` 投影成在飞 tool_call 的 `output`；前端
   `collapsedSummary(call.output)` 既有渲染（无需改 frontend）。系统收尸不带 content。
7. **CLI Ctrl-C**：`asyncio.run` 下 SIGINT 在 loop 层抛 KeyboardInterrupt，不落进 per-turn 的
   `async for`（live 暴露：仅靠 stream 循环里的 `except` 捕不到 → 留孤儿）。改用
   `loop.add_signal_handler(SIGINT)`：turn 活跃时 `kernel.interrupt`（用户发起 stop 路径），idle
   时 `raise KeyboardInterrupt` 退回默认退出；in-loop `except KeyboardInterrupt` 作兜底。interrupted
   run 返回 benign payload → CLI 留在 REPL，不掀进程，可继续敲下一句。

## 范围

派发的 `core/runs/registry.py` `sdk/kernel.py` `core/agent/runtime.py` 外，按 team-lead 批准/要求扩到：
- `core/background_tasks/registry.py`（foreground 标记 + stop_foreground_for_session）
- `core/agent/run_control.py`（user_initiated abort 标志）
- `core/session/jsonl_store.py` + `manager.py`（recovery content 解耦 + 常量）
- `platform/tools/builtins/bash.py`（前台 foreground 标记 + _ForegroundStopper 即时唤醒）
- `sdk/__init__.py`（常量再导出）
- `personal_assistant/gateway/inbound_pipeline.py` + `main.py`（IM 卡 content）
- `coding_cli/commands.py`（Ctrl-C 接线）

均**未碰** M6 的 `core/tools/registry.py` / `core/agent/liveness.py` / `realtime_stream.py`，与 M6 无交集。

## 测试

自动化全绿：
- 全树 `pytest -m "not e2e"`：**2679 passed, 0 failed, 1 skipped**（skip 为 pre-existing，无关）。
- `ruff check src/ tests/` + `ruff format --check src/ tests/`：clean。
- 端到端 DONE 硬闸（真实 `build_kernel`，`tests/integration/test_bugfix_417_interrupt_reap_e2e.py`）：
  interrupt → pgrep 无孤儿 + run cancelled + JSONL recovery `reason=interrupted` & `content`=CC 串 + 自愈 completed。
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

## 双产品 live 复验（DONE 硬闸，真 LLM proxy 127.0.0.1:4000）

worktree ephemeral 端口 + worktree config 副本 + `--auto-bind`，自起自 kill，已干净停服清产物。
一次性验收证据（pexpect 驱动 CLI / IM REST 驱动 PA），不入回归套件，下列为运行结论：

- **CLI**：`python -m coding_cli.main` 跑前台 `sleep <marker>` → Ctrl-C →
  - 子进程在 **~1.1s** 死（pgrep 无孤儿，非等 120s budget）
  - REPL 自愈：随后 "RECOVERED" 正常回复，**CLI 没退出、能继续敲下一句**
- **PA(IM+Gateway)**：IM 发前台 `sleep <marker>` → `/stop` →
  - 子进程在 **~1.1s** 死（pgrep 无孤儿）
  - IM 工具卡返回内容显示 `[Request interrupted by user for tool use]`
  - 在飞工具 badge 收口「已中断」（reason=interrupted）
  - 同会话发新消息正常回复（Req A 不回归）

## 已知项/后续

无遗留。M5 闭环：#114 中断收尾在双产品端到端可用。
