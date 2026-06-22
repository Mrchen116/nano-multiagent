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

- [ ] C1 红测：registry.kill notified/result_text + 幂等；task_stop bash/subagent 分支；RuntimeRunner on_kill 路径
- [ ] C2 实现：registry / interfaces / runtime_runner / agent.py / task_stop / wiring(_NoOpSubagentRunner)
- [ ] C3 文档：tasks 勾选 + changelog
