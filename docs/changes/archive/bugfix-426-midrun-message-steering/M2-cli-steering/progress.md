# bugfix-426-M2 — Progress

## R1 — 非阻塞 REPL 输入循环 + 运行中 steer 路由

- Context: CLI `_run_repl` 旧实现全程 `await _send_message_async` 阻塞到 run 结束（commands.py:716），运行中无法输入。目标：恢复非阻塞输入——run 推进作 task、输入循环并行读，运行中输入走 `kernel.submit(steer=True)` 注入当前 run 下一轮（决策4）。
- Decision:
  - `_run_repl` 改造：`read_line` 入 `loop.run_in_executor` 得持久 `_input_future`；run 推进封装为 `_active_run["task"]`（`_send_message_async` 新增可选 `run_id` 入参，传入则跳过 submit、只 drive 已提交的 run）。
  - 主循环 `asyncio.wait({_input_future, run_task}, FIRST_COMPLETED)`：run task 先结算渲染收尾；input 就绪时——普通消息且有同 session 活跃 run → `submit(steer=True)`（injected=True 则继续，degrade 到新 run 则 drive）；空闲 → 新 run task。
  - 会话控制命令（/exit /new /compact…）在 run 进行中先 await run 结算渲染再处理（命令是会话控制，与 steer 注入语义不同；避免运行中 /exit 丢弃在途 run 输出）。
  - abort 侧 `_on_sigint`/`interrupt()` 维持不变。M1 红利：/stop 走 interrupt() 已自动获「挂起、下次输入带上」语义，M2 不另接。
- Rationale: 决策4 钉「运行中输入必须非阻塞且走 steer=True」，编排细节（task 化 + executor input future + FIRST_COMPLETED）由 worker explore 定；未复活死代码 ReplRunQueue（与现 async REPL 结构不贴）。
- Evidence:
  - Tests: 新建 `tests/unit/test_cli_repl_steering.py` 3 测全绿（mid-run steer / idle 新 run / 连发按序）；全 CLI 套件 `-k "cli or repl"` 49 passed；全 non-e2e 树 2001 passed / 0 failed / 1 skipped。
  - Entry（真实入口，live-critical）: 真起 CLI（真实 build_cli_kernel + 真实 LLM kimiCoding:K2.6 @ 127.0.0.1:4000，权限自动放行）。第一条触发多轮 `sleep && echo stepN` 工具链；run 跑工具期间（t≈6s）输入第二条「够了，别再 sleep 了…」。结果：
    - 第一条 submit `steer=False injected=False run_id=run_183350d157b022b4`（t=0.04s）；
    - 第二条 submit `steer=True injected=True run_id=run_183350d157b022b4`（t=6.04s）—— **同一 run_id**、注入活跃 run、未另起新 run、CLI 未阻塞；
    - agent 下一轮 LLM 调用即消费第二条，回复「已经执行完第 1 步，停在这里，不再继续执行 step2/3/4」——据 steer 消息调整方向、停掉后续 sleep 工具链。
    - 直接复现 incident「运行中消息无法 steer 进当前 run」症状的消失。证据：`scratchpad/live_cli_steer.py` 运行输出（一次性验收脚本，不进套件）。
  - Frontend State Matrix / Browser QA / Visual: N/A（CLI）。
  - E2E/Regression: regression 落 `tests/unit/test_cli_repl_steering.py`（进程内真实 run drive + 可控时序 stub，覆盖 steer 路由）；真 LLM e2e 不落库（重外部依赖，按 TESTING_GUIDE 用一次性 live 验收）。
- Rollback: revert C2(R1) commit。
- Commits: C1=4a3aa41f（test）, C2=见 git log（feat R1）, C3=见 git log（docs）。

## R2 — 清理死代码 + 修结构断言

- Context: `src/coding_cli/runtime/repl_runtime.py`（ReplRunQueue/QueuedReplMessage）全仓无实例化者（死代码），决策4 把 revive-vs-delete 下放 worker。
- Decision: 删 repl_runtime.py 与空的 runtime 包；删 `test_cli_structure.py` 中断言 `ReplRunQueue.__module__` 那条（测死代码位置无回归价值，TESTING_GUIDE §1）；非阻塞输入循环行位移使 `_load_auto_mode_config_for_repl` 的 `.nanocode` 硬编码行号变化，更新 contract 白名单锚点 commands.py:1232/1233 → 1378/1379。
- Evidence:
  - Tests: `test_cli_structure.py` 5 passed；`test_no_hardcoded_workspace_dirname.py` 1 passed；全树绿（同上）。
  - 残留引用核查：`grep ReplRunQueue/QueuedReplMessage/coding_cli.runtime` 在代码与测试中无残留（仅 egg-info/SOURCES.txt 自动产物，重装刷新）。
  - 其余字段: N/A。
- Rollback: revert C2(R2) commit。
- Commits: C2(R2)=见 git log（refactor R2）。

## [Drift 记账 — out-of-unit，本 unit 按 scope 不修]

CLI 渲染存在**双订阅**同一 session stream：per-run `_send_message_async` 自调 `kernel.stream()` + 持久 `_drain_forever`（`_ensure_stream_for_session`）。这是 feat-338「单常驻 reader」设计的 drift——两条订阅并存。旧阻塞实现下 `read_line` 同步阻塞使 event loop 不转、per-run 的 stream() 调用偶然先于 drain，掩盖了脆弱性；M2 输入异步化后调度顺序翻转，暴露出 2 个 stub（`_AsyncEventingKernelStub` / `_AsyncChangedEventIdReplayKernelStub`）用 `_stream_call_count` 硬编码了「per-run 是首个 stream() 调用者」的假设。

产品行为正确：真实 `Kernel.stream()` 每订阅都 history replay 全量、调用顺序无关；`background_processor` 对 user/无 origin run 的事件全 buffer 进 pending、从不渲染（`_process_run_status` origin∈{"",user}→[]，`test_processor_ignores_user_origin_events` 守护），故双订阅不重复渲染。

按 orchestrator 决策走 **B**：改这 2 个 stub 每次 `stream()` 返回完整事件流（贴合真实 Kernel 语义），删 call_count 降级技巧（符合 TESTING_GUIDE §1「耦合内部调用顺序的测试是负债」），产品代码不动。建议**独立 refactor unit** 将 CLI 渲染收敛回单订阅（per-run 从持久 reader 单流按 run_id 取事件）；orchestrator 据此在本 PR 提 follow-up out-of-unit issue，不阻塞本 unit。

## [Fix — reviewer 反馈循环：后台 drain 健壮性]

reviewer（orchestrator）跑全树发现真回归：`pytest -m "not e2e"` collect 2759 但只跑到 ~2000 即被 KeyboardInterrupt 中断（结尾 traceback 非干净汇总）——之前误把「中断前部分通过」当全绿。

根因（systematic-debugging 复现确认）：M2 把 `_drain_forever` 改成并发后台 task，它现在也并发拉 session stream。`test_cli_async_repl_sdk.py::test_run_cli_ctrl_c_maps_to_kernel_interrupt_and_repl_survives` 的 `_CtrlCThenCancelledStream` 首次 pull 抛 `KeyboardInterrupt`（模拟用户 Ctrl-C）。`KeyboardInterrupt` 是 `BaseException`，不被 `_drain_forever` 原有的 `except asyncio.CancelledError` 接住 → 从后台 task 逃逸到事件循环 → 打断整个 pytest 会话。

判定 = 产品健壮性缺口（非测试 artifact）：后台 drain 的唯一职责是把 stream 事件搬进 bg_queue，它绝不该因 stream 抛任意异常把 REPL/进程带崩；真实用户 Ctrl-C 由 REPL 的 `_on_sigint` / `_send_message_async` 的 `KeyboardInterrupt→kernel.interrupt` 主路径处理，drain 这条旁路只需安静收尾。

修复（commands.py `_drain_forever`）：`except asyncio.CancelledError`（吞，沿用既有 teardown 写法）之后加 `except (Exception, KeyboardInterrupt) as exc:` 安静停该订阅 + `_log.debug` 记被吞异常（便于诊断静默死流）。`SystemExit` 不在 catch 内、仍传播（进程退出语义保留）。非盲目 catch-all。

regression（`test_cli_repl_steering.py::test_background_drain_stream_error_does_not_crash_repl`）：stub stream 首 pull 抛 KeyboardInterrupt，断言 `run_cli` exit 0。已验证 fix 下绿、回退 fix 该测试复现中断（KeyboardInterrupt 从 `_drain_forever` 逃逸）——真守护。contract 白名单 `.nanocode` 锚点随 fix 行位移更新 1378/1379 → 1394/1395。

验证：全 non-e2e 树 **collect == run，无 KeyboardInterrupt 中断**；CLI 套件 245 passed；新增 + 既有 Ctrl-C 测试全绿；ruff check + format 全过。

## 退出标准核对

- [x] CLI run 执行中输入 → `submit(steer=True)` 注入当前活跃 run（同 run_id、不另起、不阻塞）— live 证
- [x] 空闲输入 → 新 run（非 steer）— `test_idle_input_opens_new_run_without_steer`
- [x] run 进行中连发多条 → 按序全 steer — `test_mid_run_multiple_messages_each_steered_in_order`
- [x] abort 侧 interrupt() 未被破坏 — `_on_sigint`/`_interrupt_once` 不动，既有 Ctrl-C 测试绿
- [x] 最窄相关 CLI 单测全绿 + 真实 CLI 端到端跑通 — 上述
