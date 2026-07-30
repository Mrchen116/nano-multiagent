# M101 进度记录 — Gateway Heartbeat 调度器

## 2026-03-11
- 已按要求在编码前阅读顶层 SPEC、NodeGateway-SPEC、内核设计 SPEC、LOGBOOK、ROADMAP、COMMENTING_GUIDE。
- 在 `/Users/czj/Repos/nano-multiagent/.worktrees/M101` 先执行真实 baseline：`pytest -q tests/unit/personal_assistant`，结果 17 passed。
- 先补红测：新增 `tests/unit/personal_assistant/test_heartbeat_scheduler.py`，覆盖 `cron` / `interval` / `at`、无有效任务静默跳过、重启后 catch-up、以及多种 schedule 同时声明时报错。
- 实现 `src/personal_assistant/scheduler/heartbeat_scheduler.py` 与 `src/personal_assistant/scheduler/__init__.py`：
  - 读取各 agent workspace 下的 `HEARTBEAT.md`。
  - 支持 `interval/every`、`cron`、`at` 三种调度方式。
  - HEARTBEAT 只有标题/注释/空白时静默跳过，不创建 session、不发 run。
  - 用本地 JSON state store 记录每个 agent 的 `last_due_at`，支撑进程重启后的 missed-run catch-up。
  - `at` 任务执行后不会因 tick 或重启重复触发。
- 验证结果：
  - `pytest -q tests/unit/personal_assistant/test_heartbeat_scheduler.py` → 6 passed。
  - `pytest -q tests/unit/personal_assistant` → 23 passed。
- 负向复查：scheduler 只引入单一 canonical 结构 `src/personal_assistant/scheduler/`，未留下并行旧路径或兼容 shim。
- 产品级交互关注：当前实现会把 HEARTBEAT 指令正文直接包成一次 kernel 消息；后续接主流程时，需要补“完成后如何上报给用户替身 Agent / 用户”的产品体验闭环，否则虽然调度正确，用户侧可见反馈链仍不完整（但该项属于 M101 之外的后续集成范围）。
