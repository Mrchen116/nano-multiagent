# bugfix-417-M5: interrupt-reap-foreground — Tasks

> 对齐: ../design.md（决策 10 + 「B 升级：中断收尾」+「接口与数据流（B 增量）」+ Milestone 表 M5 行 + Changelog 顶部 M5 细化）
> delta-spec: ../specs/kernel/spec.md（运行可被中断与取消：中断收子进程 + 收口已中断 + 用户归因 content）、../specs/gateway/spec.md（/stop 中断当前运行 + 回收子进程 + 工具卡 content）、../specs/im/spec.md（工具卡按来源显示 content）

## 目标

补齐 `/stop`(kernel.interrupt) / `kernel.cancel` 的中断收尾：当前只释放会话锁（Req A 已 pass），但不杀正在跑的前台 bash 子进程（留孤儿）、不收口在飞 tool_call 徽标（停 running）。根因：interrupt 是 cooperative abort，前台 bash 的 to_thread 卡在 completed_event 不返回 → run 不结束。

外部可观察变化：
- `/stop`（IM）/ Ctrl-C（CLI）中断正在跑前台长命令 → 子进程树被杀、无孤儿、**立即**死（非等 120s budget）。
- 在飞工具徽标从「运行中」收口为「已中断」。
- 用户主动中断回填的 tool result content = CC 原串 `[Request interrupted by user for tool use]`（同份进模型 transcript + IM 工具卡）；系统中断（watchdog/崩溃）仍 `[interrupted]`，content 按来源解耦。
- 同会话中断后立即发新消息正常回复（Req A 不回归）。
- CLI Ctrl-C 中断当前轮，CLI 留在 REPL（不掀进程），可继续敲下一句。

## 退出标准

- [x] R1 红测：interrupt/cancel 定位在飞前台工具 stopper 并调（killpg 整树）；无在飞工具退化纯 abort；stopper 致退出经 M4 `_stopped` 归「已中断」（非 FAILED/tool_timeout）；core 不依赖 platform（stopper 为注入端口）。
- [x] R2 实现：`BackgroundTaskRegistry.stop_foreground_for_session`（按 session 只杀前台 blocking 任务、放过 run_background）；前台 bash `set_stop_handle(foreground=True)`（auto-bg 降级）；`RunsRegistry` 注入 `ForegroundStopper` 端口，interrupt 有在飞前台工具时杀树+置 CANCELLED+force-cancel、无则退化纯 abort，cancel 也杀树；kernel build 后 `set_foreground_stopper`。
- [x] R3 线程不滞留：前台 `_ForegroundStopper` 包装器 stop() killpg 后立即 set `completed_event` → `_run_foreground` 即时返回 interrupted（不卡 120s budget）。窄单测：永不自完成 runner，/stop 后 tool.run <5s 返回 + killpg 调用 + result interrupted。
- [x] R4 content 按来源解耦（决策 10 / Changelog）：`RunController.abort(user_initiated=)` + `is_user_interrupt`；interrupt 标 user_initiated；runtime `_recover_orphaned_tool_calls` 透传 → `append_tool_call_recovery(content=)` → jsonl 合成优先 content（fallback `[{reason}]`）；`USER_INTERRUPT_RECOVERY_CONTENT` 常量经 sdk 再导出。用户 vs 系统两路单测。
- [x] R5 IM 工具卡 content：gateway `/stop` 标记 user-interrupted run，`_emit_terminal_reconcile` 对其带 content → `main.py` reconcile 投影成 tool_call `output`（前端 collapsedSummary 已渲染，无需改 frontend）；系统收尸不带 content。observer 两路单测。
- [x] R6 CLI Ctrl-C 接线：`commands.py` turn 流式循环 catch KeyboardInterrupt → `kernel.interrupt`（in-loop 兜底）+ asyncio `loop.add_signal_handler(SIGINT)`（asyncio.run 下 SIGINT 不落 per-turn async for，必须 signal handler）→ turn 活跃时 interrupt、idle 退默认退出；interrupted run 返回 benign payload，CLI 留 REPL。CLI 单测。
- [x] R7 端到端 DONE 硬闸（真实 build_kernel）：interrupt → pgrep 无孤儿 + run cancelled + JSONL tool_call_recovery reason=interrupted & content=CC 串 + 同会话自愈 completed。
- [x] 收尾：CLI + PA 双产品 live 端到端复验（真 LLM proxy）。

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  - `stop_foreground_for_session` 只杀前台 blocking 任务、按 session 作用域、忽略终态、放过 background。
  - interrupt 有在飞前台工具时 force-cancel 释锁 + 杀树；无时退化纯 abort（stop_reason=aborted 不回归）；cancel 也触发前台 stopper。
  - 前台 stopper 致退出经 `_stopped` 归「已中断」、`_run_foreground` 即时返回不滞留线程。
  - 用户中断回填 CC content / 系统中断回填 `[interrupted]`（badge 都 interrupted）。
  - gateway reconcile 对 user-interrupted run 带 content → tool card output；系统不带。
  - CLI Ctrl-C → kernel.interrupt 且 REPL 存活。
  - **端到端（真实 build_kernel）**：interrupt → 无孤儿 + cancelled + JSONL recovery content=CC 串 + 自愈。
- 已有/新增测试：
  - `tests/unit/agent/background_tasks/test_background_tasks.py`（`stop_foreground_for_session` 四例）。
  - `tests/unit/test_run_cancel.py`（interrupt force-cancel / 退化 abort / cancel 杀树）。
  - `tests/unit/agent/tools/test_bash_tool.py`（前台 stopper 即时唤醒、不滞留线程）。
  - `tests/unit/test_session_manager.py`（content 解耦：user vs system 两路）。
  - `tests/unit/test_inbound_pipeline_streaming.py` + `tests/unit/personal_assistant/test_inbound_pipeline_user_interrupt_content.py`（gateway reconcile content 两路）。
  - `tests/unit/test_cli_async_repl_sdk.py`（CLI Ctrl-C → interrupt + REPL 存活）。
  - `tests/integration/test_bugfix_417_interrupt_reap_e2e.py`（真实 build_kernel 端到端 DONE 闸，理由：跨 kernel.interrupt→registry→stopper→bash to_thread→runtime finally→JSONL recovery 多层，孤立单测覆盖不到这条缝；用 fake model client，不挂 e2e marker）。
- 落层/目录/marker：tests/unit/（kernel/gateway/CLI 各单测）、tests/integration/（build_kernel 端到端，无需真实 LLM 上游 → fake client，不挂 e2e marker）。
- 可选依赖 importorskip：无。
- 本 milestone 一次性验收证据（收尾删除、不进套件）：CLI/PA live 复验日志（记 progress.md，不入套件；pexpect 驱动 CLI、IM REST 驱动 PA）。

前端 UI：本 milestone 不新增 UI 组件。IM 工具卡 content 复用既有 `ToolCall.output`/collapsedSummary 渲染（无需改 frontend）；badge 映射 `interrupted→已中断` M3 已建。故 frontend 仅 live 浏览器外的 REST 断言核对一次（PA live 校验工具卡 content），无新组件/无 vitest 改动。

## Roadpoints

| R | 标题 | 状态 |
|---|---|---|
| R1 | 红测（interrupt/cancel 收前台子进程 + 收口徽标 + 退化 + 端口注入） | DONE |
| R2 | stop_foreground_for_session + interrupt/cancel 前台收尾 + kernel 注入 | DONE |
| R3 | 前台中断不滞留线程（即时唤醒 completed_event） | DONE |
| R4 | content 按来源解耦（用户 CC 串 / 系统 interrupted） | DONE |
| R5 | IM 工具卡显示用户中断 content（gateway reconcile → output） | DONE |
| R6 | CLI Ctrl-C → kernel.interrupt（asyncio signal handler + REPL 存活） | DONE |
| R7 | build_kernel 端到端 DONE 硬闸 | DONE |
