# M1-fix: drain_run 硬墙钟超时改为空闲超时

## 目标

把 `drain_run()` 的超时语义从"整个 run 的绝对墙钟上限"改为"空闲超时"：每收到一个
该 run_id 的事件就把 deadline 重置为 `now + idle_timeout`；只有连续 idle_timeout 秒
没有任何该 run 的事件才判定卡死并抛 TimeoutError。不设绝对墙钟上限。

## 退出标准

1. `drain_run()` 默认 idle_timeout = 1800s，每收到该 run 的事件就重置 deadline。
2. 真正卡死（超过 idle_timeout 无事件）仍抛 TimeoutError。
3. `commands.py` 两处 `terminal_timeout=120.0` 更新为 1800.0（或使用新默认值）。
4. 单测覆盖：① 长时间持续有事件不被超时（原 bug 回归）；② 真卡死仍能超时。
5. 现有测试全绿（不破坏已有用例）。

## 测试策略

- 任务类型：Bug 修复（纯逻辑，后端）
- 测试位置：`tests/unit/test_session_stream.py`（现有文件，补充新用例）
- 关键用例：
  - `test_drain_run_long_run_not_killed_by_idle_timeout`：模拟长时间持续有事件的 run，
    用小 idle_timeout 注入，在 idle 期间内持续喂事件，验证不触发超时
  - `test_drain_run_idle_timeout_triggers_when_no_events`：模拟事件停止流出超过
    idle_timeout，验证抛 TimeoutError
- 时钟/sleep 控制：通过 `idle_timeout` 参数注入小值（如 0.1s）控制测试速度，
  不实际 sleep 1800s

## Roadpoints

| ID | 标题 | 状态 |
|----|------|------|
| R1 | 新增失败测试（Red）| DONE |
| R2 | 修改 drain_run 为空闲超时实现（Green）| DONE |
| R3 | 更新 commands.py 两处调用 + 补文档 | DONE |
