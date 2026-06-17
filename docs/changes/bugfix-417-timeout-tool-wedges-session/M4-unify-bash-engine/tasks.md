# bugfix-417-M4: unify-bash-engine — Tasks

> 对齐: ../design.md（决策 8/9 + 「接口与数据流（A 增量）」+ Milestone 表 M4 行）

## 目标

把 bash 心跳/killpg/超时 reason 这些能力从生产**死路**（`bash_runner.py` 的 `run_stream` / bash.py 的 `_run_legacy_sync` / `wiring is None` 分支）重落到唯一生产引擎 ShellRunner，删死路，让 M3 已活的 executor→publisher→watchdog 链真正接到 bash 源。外部可观察变化：
- 生产路径跑静默长命令（`sleep 200`）不再被 120s watchdog 误杀（gateway.log/`kernel.stream` 真有 `run_heartbeat`）。
- bash 超时（`timeout 5 sleep 200`）→ IM `tool_call.reason=tool_timeout` → 前端「执行超时」。
- 派生子进程命令（`npm run build` 类）超时整树回收、无孤儿、会话可继续。
- CLI 与 PA 双产品 bash 输出/退出码/截断/停止语义不变。

## 退出标准

- [ ] R1 硬化 ShellRunner：`start_new_session=True` + killpg 杀整组（判整组存活，SIGTERM 宽限→SIGKILL）+ 非阻塞 drain + 超时带可区分信号；最小侵入 pump→文件模型（决策 9）。单测改打 ShellRunner 全绿。
- [ ] R2 `_run_foreground` 等待期带心跳轮询（复用 M3 `run_coroutine_threadsafe` 桥，经 `ctx.emit_execution_event` 发 `phase:running`，不另起新路）；超时→`reason_code=tool_timeout` 贯通。
- [ ] R3 删 `run_stream` + `_run_legacy_sync` + `wiring is None` 分支（grep 确认零生产调用方后）；ShellRunner docstring 明写「前台+后台唯一 bash 引擎，bash_runner.py 已删」。
- [ ] R4 经真实 `build_kernel` wiring 的端到端集成测试（DONE 硬闸）：静默长命令断言 `kernel.stream` 真冒 `run_heartbeat`；bash timeout 断言 `tool_call.reason=tool_timeout`。
- [ ] R5 reason 常量盘点 + 收尸 content 措辞与徽标一致（消 `watchdog_timeout`≠`stalled` 不一致）。
- [ ] 收尾：CLI + PA 双产品 live 端到端复验（bash 输出/退出码/截断/停止逐条不变；长静默不误杀；超时→「执行超时」；派生子进程整树回收）。

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  - ShellRunner 超时杀整个进程组（含派生孙进程，无孤儿持写端致挂死）。
  - ShellRunner 非阻塞 drain 在孤儿持写端时仍在时限内解封。
  - ShellRunner 执行期产生 `phase:running` 心跳信号、超时回 `on_fail` 带可区分超时标志。
  - `_run_foreground` 等待期周期发 `phase:running` 经 ctx 回调；超时 ToolError 带 `reason_code=tool_timeout`。
  - **端到端（真实 build_kernel）**：静默长命令 → `kernel.stream` 冒 `run_heartbeat`；bash timeout → tool_call/`tool_end` 事件携 `reason=tool_timeout`。
- 已有测试在：
  - `tests/unit/agent/background_tasks/test_platform_adapters.py`（ShellRunner 现有覆盖，扩展 R1）。
  - `tests/unit/agent/tools/test_bash_tool.py`（BashTool 路径，扩展 R2）。
  - 死路相关单测（`test_bash_runner.py` 等）随 R3 删/改打 ShellRunner。
  - 端到端新建 `tests/integration/test_bugfix_417_bash_engine_e2e.py`（真实 build_kernel wiring，R4），理由：跨 build_kernel→ShellRunner→ctx→executor→publisher→stream 五层，现有孤立单测覆盖不到这条缝（B1 失败正源于此）。
- 落层/目录/marker：tests/unit/（ShellRunner、BashTool）、tests/integration/（build_kernel 端到端，无需真实 LLM 上游 → 用 fake model client，不挂 e2e marker）。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：CLI/PA live 复验日志/截图（记 progress.md，不入套件）。

前端 UI：本 milestone 仅碰 IM reason 常量/措辞（R5），无新 UI 组件。徽标映射（`tool_timeout→执行超时`/`stalled→已中断`）M3 已建且单测覆盖；R5 若动文案需真实浏览器核对一次。其余 N/A。

## Roadpoints

| R | 标题 | 状态 |
|---|---|---|
| R1 | 硬化 ShellRunner（killpg+drain+心跳源+超时信号） | TODO |
| R2 | `_run_foreground` 接心跳轮询 + reason_code 贯通 | TODO |
| R3 | 删死路 run_stream/_run_legacy_sync/wiring=None + docstring | TODO |
| R4 | build_kernel 端到端集成测试（DONE 硬闸） | TODO |
| R5 | reason 常量盘点 + 收尸措辞一致 | TODO |
