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

## R4 — build_kernel 端到端集成测试（DONE 硬闸）

- Context: 决策 8 测试策略——本事故本质=单测全绿/live 全红。心跳链横跨 build_kernel→ShellRunner→ctx→executor 桥→realtime_stream→kernel.stream 五层，孤立单测证不到它真到 watchdog（B1 失败正是此）。守卫不能只押人手 live。
- Decision: 新建 tests/integration/test_bugfix_417_bash_engine_e2e.py，经真实 build_kernel wiring（_llm_client_override 发 bash tool_call）驱动整轮，消费 kernel.stream 断言：① 静默长命令冒 run_heartbeat；② bash timeout 的 tool_end 携 reason_code=tool_timeout。
- Rationale: 这两条恰好是 round-1 reviewer FAIL 的 B1/C1 的可观察投影。fake LLM 不需真实上游（非 e2e marker，无外部服务），可进 CI 回归。
- 实施期踩坑（记 LOGBOOK 价值）：① loop 把「content='' 且 finish_reason 非 None」当终态元数据帧跳过 → fake LLM 必须先发 finish_reason=None 的 tool_call 帧、再发终态帧（仿真实 provider 流式形态），否则 tool_call 被吞、整轮只有 run_status。② kernel.stream 是 live 订阅、不随 run 终态自动关，collector 要并发跑 + 等终态 status 后再 stop + 补发一条 noop 解 anext 阻塞再 drain，避免「停早了只收到前 2 个 run_status」的竞态。
- Evidence:
  - Tests: 2 passed，连跑 3 次稳定（5.14s）。真链路验证 run_heartbeat + tool_end.reason_code=tool_timeout 端到端到达 stream。
  - Entry: 这本身就是 build_kernel 真实入口测试。
  - Frontend/Browser/Visual: N/A
  - E2E/Regression: 本测试即 DONE 硬闸回归。
- Rollback: 删该测试文件。
- Commits: C1/C2 合一=7ead9fde（test 即守卫，行为已由 R1/R2 实现），C3=(本次 docs)
- Next: R3（删死路，待 orchestrator 决 R3 截断契约归属 A/B）+ R5。

## R3 — 删死路（bash_runner.py + _run_legacy_sync + wiring=None）

- Context: 死路 bash_runner.run_stream / _run_legacy_sync / wiring=None 分支是生产从不走的第二套 bash 引擎，正是它让 M2/M3 修在死路、骗过单测、live 全挂。决策 8 要求删它、ShellRunner 成唯一引擎。
- [Design 决策落地] 截断契约归属取 B（result-budget 为生产唯一截断真源）：实测生产 wired 路径对 2MB 输出 truncated:False、无 fullOutputPath——死路的 bash 行/字节截断 + fullOutputPath + 1MB 硬上限 + 'Command aborted' ToolError 全是死路独有、生产从来没有。移植它们（A）会与既有 result-budget 造两套截断，违反决策 9「最小侵入」+ §0.1「不造平行物」。故删这些「测死代码」的契约/集成测试；signal/timeout/exitCode/non-zero/reason_code 等真契约在生产 wired 路径重新覆盖（runs_registry=None 拿真 ShellRunner）。截断由 result-budget 兜底，已被 test_tool_result_budget 覆盖。orchestrator 放行确认与定稿设计一致。
- Decision:
  - 删整文件 bash_runner.py；bash.py 删 wiring=None 分支 + _run_legacy_sync + _get_bash_runner + _bash_runner 字段 + 孤儿 _build_error_details + 死类 import；run() 前台无条件走 _run_foreground（_require_wiring 无 wiring 大声报错）。
  - 改打生产引擎：test_bash_tool / test_tools_bash_task / contract / integration / risk_gate 的执行型用例全部走 wire_background_tasks(runs_registry=None) 的真 ShellRunner；no-wiring 用例改为断言「大声报错」。
  - 删死路专属断言：行/字节截断、fullOutputPath、1MB 硬上限、Command aborted。
  - safety.py / safety_types.py prose 指针从已删 bash_runner 更正到 ShellRunner。
- Rationale: 唯一生产引擎，杜绝「下次再漏一处」。删的是死代码（零用户影响，全树 collect 2662 通过、grep 零生产调用方验证）。
- Evidence:
  - **截断契约实测取证（决策 B 的事实依据，reviewer/verifier 据此判「截断语义不变」）**：
    - `_run_foreground`（生产，bash.py）硬编码 `truncated:False`、无 `fullOutputPath`；`_run_legacy_sync`（死路，已删）才有行/字节截断 + `fullOutputPath`。
    - 实测真 wiring 跑 5000 行（≈405K 字符）输出：keys=['exitCode','stderr','stdout','truncated']、`truncated:False`、stdout 完整 404999 字符、无 `fullOutputPath`；跑 2MB 单行：同样 `truncated:False`、完整 2097152 字符。证明行/字节截断 + fullOutputPath 生产从未执行。
    - 全仓零生产消费方：前端不渲染 `truncated`/`fullOutputPath`（只按 result-budget 压制后的 stdout）；`CommandExecution` 仅 safety.py dataclass 字段声明 + 死路用。
    - 生产截断真源 = result-budget（registry.py:77，bash `max_result_size_chars=30000`），由 `tests/unit/test_tool_result_budget.py` 覆盖。
  - **决策 B（orchestrator 拍板，判据记 unit design.md Changelog da13d285）**：「截断语义逐条回归不变」判据 = 生产 result-budget 截断不变（30K 压制），非死路行/字节截断+fullOutputPath。删 fullOutputPath+行/字节截断对生产零用户可见影响（生产从未执行那段）；移植它=造与 result-budget 并行的第二套截断=技术债，违背架构最优。
  - **真活契约移植清单（B 硬要求，不丢）**：signal details（`exitCode=-SIGTERM`/`signal`/`signalNumber`）、timeout details（`timedOut`/`timeout`/`reason_code=tool_timeout`）、exitCode/non-zero、stdout+stderr 合并——全部移到生产 wired 路径（`_wired_bash_tool` = wire_background_tasks(runs_registry=None) 真 ShellRunner）重新覆盖：`tests/contract/test_tools_bash_contract.py`（timeout+signal）、`tests/integration/test_tools_bash_integration.py`（signal）、`tests/unit/test_tools_bash_task.py`（non-zero/timeout/stdout-stderr 合并/no-timeout 完成/no-wiring 大声报错）。
  - **删清单（死路独有，生产从未有）**：行/字节截断、fullOutputPath、1MB 硬上限、'Command aborted' ToolError、整文件 test_bash_runner.py。
  - Tests: bash 相关 29 passed（含 R4 e2e）；全树 collect 2662 无 import 错误；ruff 干净。
  - Entry: R4 build_kernel 端到端守卫覆盖真入口。
  - Frontend/Browser/Visual: N/A
  - E2E/Regression: R4 e2e 守卫；result-budget 截断由 test_tool_result_budget 守卫。
- Rollback: 回退到 8dfe0659（R2 C2）恢复死路（无害，仅留技术债）。
- Commits: C1=1684a9cd, C2=2c297851, C3=(本次 docs) + 漏网修复 test_bash_check_permissions_integration（见 git log）
- Next: R5 — reason 常量盘点 + 收尸 content 措辞核对。

## R5 — reason 常量盘点 + 收尸措辞核对

- Context: design 要求消 watchdog_timeout≠stalled 不一致；orchestrator 确认 M3 已做 badge 一致性，R5 只需消语义重叠 + 收尸 content 措辞核对。
- 盘点结论：① 生产已无 'timed_out' 作 tool_call reason（M3 改 stalled），前端保 timed_out 仅为旧持久化行的 legacy key（已标注）。② 唯一真重叠：IM relay watchdog 兜底失败 reason='watchdog_timeout' vs Gateway watchdog='stalled'，同语义（idle 丢 liveness 被收）两词汇。③ semantic='relay_watchdog_timeout' 标的是「哪条路径」非 reason，不重叠，保留。④ 前端不消费 relay 的 reason/semantic（仅按 progress_state/detail 渲染），故对齐无用户可见变化。⑤ 收尸只落 reason，用户标签全由前端 reason→label 产出（stalled/interrupted→已中断，tool_timeout→执行超时），无 content 文案与徽标不一致。
- Decision（§FL 单 commit）：relay watchdog reason 'watchdog_timeout'→'stalled'；订正 main.py reconcile + 残留注释里把 timed_out 当现行 reason 的陈述。
- Rationale: 纯内部 reason 词汇一致性，前端不 key 这些字段；§FL 判据满足（单点、无可断言行为变化的契约改动→省三提交，注释/词汇对齐）。
- Evidence:
  - Tests: relay_watchdog + repositories_message + permission_watchdog + inbound_streaming 46 passed；ruff 干净。
  - Entry/Frontend/Browser/Visual/E2E: N/A（内部词汇；badge 一致性 M3 已建+单测覆盖）。
- Rollback: 回退本 commit。
- Commits: 单 commit=4d1b9d36（§FL，省略 §0.4 三提交，理由：单点 reason 对齐 + 注释订正）。
- Next: 全测试树 sweep + CLI/PA 双产品 live 端到端复验。

## 收尾 — 全测试树 + live 复验状态

- 全测试树（`pytest -m "not e2e"`）：2656 passed / 2 skipped / 0 failed；全树 collect 2662 无 import 错误；ruff check 干净。含 R4 build_kernel 端到端守卫真链路通过（run_heartbeat 进 stream + tool_end.reason=tool_timeout）。
- R3 删死路漏网修复：test_bash_check_permissions_integration 的 _make_registry 注册无 wiring BashTool，执行型用例改打 wired ShellRunner（commit 见 git log）。
- **CLI + PA 双产品 live 复验：env 受阻待解**。LLM proxy（:4000）未运行，`~/Repos/LLM_PROXY/start_proxy.py` 需用户 OAuth 凭证，不宜由 worker 代起；fixtures 仅错误注入桩，不能驱动真实 agent 轮次。已 SendMessage orchestrator（按 §0.11 不降级凑 DONE）：请其起 proxy 后我跑两套 live 旅程，或确认 R4 自动化守卫已充当 DONE 硬闸、live 由有 proxy 环境另验。
- live 复验 env 插件已预演就绪：scripts/free-ports.sh 正常、yq 可用、主 config 有 llm: 段指向 :4000——proxy 一起即可立即执行 CLI（普通/长静默/超时/Ctrl-C）+ PA（IM+Gateway worktree ephemeral 端口 + auto-bind，sleep 200 / timeout 5 sleep 200 / npm run build 类，验 gateway.log run_heartbeat + IM reason=tool_timeout + 派生子进程整树回收）。

## Live 复验 — 证据（LLM proxy 起后执行）

### CLI live（3/3 通过）
- 普通命令 `echo hello-from-live-cli`：tool bash 执行，输出正确，state completed。
- 超时 `sleep 30` timeout=2：报 "Command timed out after 2 seconds"（tool_timeout 路径），agent 恢复、会话继续。
- 派生子进程 `sleep 300 & wait` timeout=2：超时后整树回收，`pgrep -x sleep` 零孤儿（Req D）。

### PA live（IM+Gateway, worktree ephemeral 端口 + auto-bind）
- 普通 bash 往返：`echo hello-from-PA-live` → agent 回 bash completed + 输出正确，full stack 通。
- **B1 静默长命令不被误杀（决定性）**：发 `sleep 140`（> 120s Gateway watchdog）。监控 conversation_events：run.heartbeat 随时间稳定增长 8→18（≈每 10s 一跳，与设计一致），跨过 t=120s watchdog 窗口，**relay.failed 全程 =0**，命令正常完成。证明心跳令 watchdog 见 liveness、不误杀活着但安静的 run。`sleep 60` 同样产 6 跳心跳并 completed。
- C1/Req D PA 侧：见下条（timeout→reason=tool_timeout、派生子进程整树回收）。
