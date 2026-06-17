# bugfix-417-M4 — Progress

> 启动上下文核实（§2.3 完成）：
> - 死路确认：`run_stream`/`_run_legacy_sync` 仅被 bash.py 自身 `wiring is None` 分支 + 单测调用，零其它生产调用方（loader.py 无引用）。
> - M3 下游链全活：executor `run_coroutine_threadsafe` 桥（tools/registry.py:213）、realtime_stream `on_tool_execution_update→run_heartbeat`、liveness 模块 LLM-await（loop.py:320）+ permission ticker（runtime.py:1448）、gateway `stalled`（inbound_pipeline.py:869）、前端徽标（tool-calls-panel.tsx:83）。
> - M4 = 把 bash 源从死路换到 ShellRunner 接活链 + 删死路 + 端到端守卫。

## R1 — 硬化 ShellRunner（killpg + 非阻塞解封）

- Context: M2 的进程组治理（start_new_session/killpg/非阻塞 drain）落在生产死路 `bash_runner.run_stream`，生产引擎 ShellRunner 一项没有 → 派生子进程超时不整树回收、孤儿持写端致执行线程挂死。
- Decision: 把同样的不变量重落到 ShellRunner（决策 8）。保 pump→文件 I/O 模型（决策 9 最小侵入）：
  - `Popen(start_new_session=True)` 让子 bash 成独立进程组 leader。
  - 超时/stop 用 `os.killpg(-pgid)` SIGTERM 宽限→SIGKILL 杀整组（移植死路已验证的 `_kill_process_group`）。
  - killpg 后关 Popen 读端 fd 让阻塞 `pump.read` 见 EOF 解封 + `join` 超时兜底 → drain 不挂死（替代死路的 selector `_drain_nonblocking`，pump 模型下关 fd 更贴合）。
- Rationale: 统一到唯一生产引擎，杜绝"修在死路、live 全挂"。pump 模型不动，回显/截断/计时语义零扰动。
- 回归修复（实施期发现）：blocking `_kill_process_group` 让 stop 调用方等宽限期间 monitor `process.wait()` 先返回 → `on_fail` 抢写 FAILED，stop→KILLED 语义被改。修法：stop 路径的整组回收放后台线程异步做，调用方立即返回让 `registry.kill` 先落 KILLED；timeout 路径（`_monitor` 内）仍同步等宽限不变。非 design 偏差，是 ShellRunner 与 BashRunner 生死管理范式差异（ShellRunner 有 monitor 线程 + registry 终态 guard，BashRunner 无）下的接缝处理。
- Evidence:
  - Tests: `tests/unit/agent/background_tasks/test_platform_adapters.py` 新增 3 测全绿（独立进程组 / 超时杀孙进程树 / 孤儿持写端 drain 不挂死）；bash+shell+background 全套 284 passed 无回归（含 test_task_stop KILLED 语义）。
  - Entry: build_kernel 端到端入口在 R4 统一验。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: R4 端到端集成测试守卫。
  - Visual/Interaction: N/A
- Rollback: 回退到 73a3f7f4（plan commit）。
- Commits: C1=e0af063e, C2=64920a96, C3=(本次 docs)
- Next: R2 — `_run_foreground` 接心跳轮询 + reason_code 贯通。

## R2 — _run_foreground 接 bash liveness 心跳 + 超时 reason_code

- Context: 生产前台 bash 走 _run_foreground，它只 completed_event.wait(120) 阻塞、零事件，且失败路径无 reason_code。死路 _run_legacy_sync 的 run_stream on_event 心跳 + tool_timeout reason 全在死路上，生产一项没有 → B1（静默长命令零心跳被误杀）、C1（超时 reason=null）。
- Decision:
  - 把 wait(120) 改成按 _FOREGROUND_HEARTBEAT_INTERVAL(10s) 轮询的循环，每 tick 经 ctx.emit_execution_event 发 phase:running（带 elapsed_ms/command）。
  - 失败路径检测 ShellRunner on_fail 的 "timed out after Xs"，分流为带 reason_code=tool_timeout 的超时 ToolError（与 _run_legacy_sync 现做法一致）。
- Rationale: 复用 M3 已建活链——executor 已把 ctx.emit_execution_event 经 run_coroutine_threadsafe 桥回 loop → tool_execution_update → realtime_stream on_tool_execution_update → run_heartbeat 进 stream → 两 watchdog 重置。M4 只补 bash 源这一段，不另造通路（design「接口与数据流（A 增量）」前台等待 liveness 条目）。心跳间隔 10s ≪ watchdog 120s。
- Evidence:
  - Tests: test_bash_tool.py 10 passed（含新 2 测：心跳 phase:running 真发出 / 超时带 reason_code=tool_timeout）；bash+心跳+watchdog+inbound 相关 454 passed 无回归。
  - Entry: build_kernel 端到端真链路在 R4 验。
  - Frontend State Matrix / Browser QA / Visual: N/A（R5 才碰 IM 措辞）。
  - E2E/Regression: R4 守卫。
- Rollback: 回退到 64920a96（R1 C2）。
- Commits: C1=e74b5551, C2=8dfe0659, C3=(本次 docs)
- Next: R3 — 删死路 run_stream/_run_legacy_sync/wiring=None + ShellRunner docstring。
