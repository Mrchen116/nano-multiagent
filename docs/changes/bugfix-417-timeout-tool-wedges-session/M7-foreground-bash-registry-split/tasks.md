# bugfix-417-M7: 前台 bash 退出 BackgroundTaskRegistry — Tasks

> 对齐: ../design.md（决策 12 / C 升级整段）

## 目标

前台 bash 不再寄生 `BackgroundTaskRegistry`。新建职责极窄的 `ForegroundExecutionRegistry`（core 层，只持「在飞前台子进程 killpg 句柄 + session 映射」），前台命令的完成/失败/超时/中断只经 `tool result` 同步返回——物理上不再有 `<task-notification>` 通道。仅当前台预算耗尽真转后台（auto-background）那一刻，才显式移交进 `BackgroundTaskRegistry`，此时按后台任务发一次通知。

外部观察者能看到：前台命令超时/失败时 IM 工具卡只出**一次**结果，不再额外冒后台完成通知（双通道 bug 消失）。

## 退出标准

- [ ] `ForegroundExecutionRegistry`（`register` / `unregister` / `stop_for_session(session_id)->bool`，core 层、不依赖 platform）单测全绿
- [ ] `_run_foreground` 不再 `register_bash` / `set_stop_handle` 进后台 registry、改登记 fg registry 的单测
- [ ] auto-background 单锁原子移交（unregister→register_bash→mark_running→set_stop_handle→切回调，notified 默认 False）+ 移交与回调竞态（预算耗尽瞬间命令恰好完成→不丢不双投）单测
- [ ] `BackgroundTaskRegistry` 删前台补丁（`_foreground_task_ids` / `set_stop_handle(foreground=)` / 三处 discard / `stop_foreground_for_session`）后全量单测改打新路径仍绿
- [ ] `kernel.py` foreground_stopper 注入改向 `ForegroundExecutionRegistry.stop_for_session`、`runs/registry.py` 零改动的接线单测
- [ ] 端到端守卫（DONE 硬闸）：经真实 build_kernel wiring 跑前台 bash 超时 → kernel.stream 只出工具结果、不投 `<task-notification>`；跑 `run_in_background` 命令 → 仍投 `<task-notification>`
- [ ] CLI/PA 双产品 live 复验：前台超时单通道（proxy log 无 task-notification）+ /stop 中断（pgrep=0 + 徽标「已中断」+ 会话自愈）+ 后台任务通知正常
- [ ] 全树 pytest -m "not e2e" 全绿；ruff check + ruff format 绿

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  - fg registry 的 register/unregister/stop_for_session 语义（按 session 命中、放过其它 session、放过已注销、未命中返回 False）
  - 前台 bash 走 fg registry 而非后台 registry（后台 registry 无该任务记录）
  - auto-background 移交后任务进后台 registry、fg registry 已注销、通知正确（一次、不双投、不丢）
  - 移交/回调竞态：预算耗尽瞬间命令完成 → 结果不丢不双投
  - /stop 中断前台 → fg stopper 杀子进程 + 唤醒 waiter（M5 行为在新 registry 下不回归）
  - 后台 registry 删前台补丁后真后台路径（run_in_background + task_stop）不回归
  - kernel 注入改向后 runs/registry interrupt/cancel 零改动仍工作
  - 双通道负向不变量：前台超时只出 tool 结果、不投 task-notification
- 已有测试在：
  - `tests/unit/agent/background_tasks/test_background_tasks.py`（删/迁前台 stop-by-session 段 + foreground_marker 段）
  - 新建 `tests/unit/agent/background_tasks/test_foreground_registry.py`（fg registry 单测，理由：新类，独立行为面）
  - `tests/unit/agent/tools/test_bash_tool.py`（interrupt 用例改打 fg registry + 新增 auto-bg 移交/竞态用例）
  - `tests/integration/test_bugfix_417_bash_engine_e2e.py`（扩 M7 DONE 硬闸两条）
- 落层/目录/marker：tests/unit/ + tests/integration/（沿用现有 e2e 文件，非 e2e marker）
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：CLI/PA live 的 proxy log / 截图（记 progress，不进套件）

前端：N/A（纯内核库结构重构，IM 工具卡行为由端到端守卫 + live 复验覆盖，本 milestone 不改前端代码）

## Roadpoints

### R1 — ForegroundExecutionRegistry（core，新建）+ 单测

- 步骤: 新建 `core/background_tasks/foreground_registry.py`；定义 `ForegroundExecutionRegistry`，持 `{session_id: [stopper]}`，提供 `register(session_id, stopper)` / `unregister(session_id, stopper=None)` / `stop_for_session(session_id)->bool`；新建单测文件
- 验证: 红测试覆盖 register/stop_for_session 命中、scope 到 session、未命中返回 False、unregister 后不再命中

### R2 — bash.py 前台改登记 fg registry + auto-bg 显式移交

- 步骤: `_run_foreground` 改登记 fg registry（不进后台 registry）；on_complete/on_fail 只 set completed_event / 填 result_holder（去 notified）；auto-bg 单锁原子移交进后台 registry；wiring.py 装配 fg registry
- 验证: 前台命令完成后后台 registry 无记录；auto-bg 后任务进后台 registry + fg 已注销 + 通知正确；移交/回调竞态不丢不双投；/stop 中断在新 registry 下唤醒 waiter

### R3 — BackgroundTaskRegistry 删前台补丁 + kernel 注入改向

- 步骤: 删 `_foreground_task_ids` / `set_stop_handle(foreground=)` 分支 / 三处 discard / `stop_foreground_for_session`；kernel.py:431 注入改向 fg registry；迁移/删除 test_background_tasks.py 的前台段
- 验证: 后台 registry 全量单测改打新路径仍绿；真后台路径（run_in_background + task_stop）不回归；kernel 接线单测

### R4 — 端到端 DONE 硬闸 + 全树 + live

- 步骤: 扩 e2e 加「前台超时只出 tool 结果不投 task-notification」+「run_in_background 仍投 task-notification」两条；跑全树 + ruff；CLI/PA live 复验
- 验证: 端到端守卫绿；全树 -m "not e2e" 绿；ruff 绿；live 三项证据记 progress
