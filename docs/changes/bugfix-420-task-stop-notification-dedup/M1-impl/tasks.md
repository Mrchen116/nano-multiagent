# bugfix-420-M1 — impl tasks

> 对齐 design.md 的 4 条关键决策。单 M1，跨 core+platform。

## 测试策略

测什么（落 `tests/unit/`，回归层）：
- registry.kill() 扩参 `notified` / `result_text`：携带能力 + 抑制能力 + 幂等不破（二次终态转换 no-op）。
- task_stop 工具按 task_type 分支：bash 同步 `kill(notified=True)` 抑制通知；subagent 不同步 kill（record 不进终态，留给 worker unwind）。
- RuntimeRunner worker abort 分支：`controller.is_aborted` 为真走 `on_kill(result_text=最后一段文字)`；自然完成走 `on_complete` 不被误标 killed；无产出时 result_text=None（→ `<result>` 省略）。

不测（已有覆盖 / 非本 unit 行为）：
- `_NotifyingStore` notified=True 抑制投递（既有 `test_notifying_store_skips_deliver_when_notified_true` 覆盖，bash 抑制即复用此机制）。
- `<result>` 由 `result_text` 非空驱动的渲染（既有 `notifications.py` + 测试覆盖；本 unit 不改 notifications）。
- 前台双通道（bugfix-417 范围）。

## Tasks

- [x] C1 红测：registry.kill notified/result_text + 幂等；task_stop bash/subagent 分支；RuntimeRunner on_kill 路径
- [x] C2 实现：registry / interfaces / runtime_runner / agent.py / task_stop / wiring(_NoOpSubagentRunner) + runners.py 模板
- [x] C3 文档：tasks 勾选 + design changelog

## 实现说明（与 design 的微调）

- design 写 `controller.is_aborted()`，实际 `run_control.py:70` 是 `@property`，实现用无括号 `controller.is_aborted`。
- `notifications.py` 无需改：`<result>` 已由 `record.result_text` 非空驱动，`result_text=None` 自动省略，满足「无产出省略」场景。
- 额外动了两处 design 未点名但属同一契约的文件：`core/background_tasks/runners.py`（`run_subagent_lifecycle` 模板同步加 `on_kill` 形参，保持协议一致）、`tests/integration/background_tasks/test_task_stop.py`（两个整合测试断言的是旧（buggy）行为，更新为新契约：bash 不投递通知、subagent 经 worker unwind 进 KILLED 且通知带 `<result>`）。
- 验收：`pytest -q tests/unit -k "background_task or task_stop or registry"` 140 passed；全测试树 `-m "not e2e"` 2722 passed / 1 skipped；ruff check + format 全过。
