# feat-394-M8: fix-round6 Tasks

## 目标

修复 R6-1（_IntervalSchedule ceil bug 导致首次触发后永不再触发）、R6-2（cron awareness 未注入）、CRITICAL-1（合约白名单行号失配），并 live 验证 recurring 连续触发。

## 退出标准

- `_IntervalSchedule.due_times_up_to` 改用 floor，elapsed=interval+overhead 仍触发
- 大 gap 只触发一次（不补跑）
- cron awareness 优先从 `_canonical_session_store` 取 session_id
- 合约白名单行号 703 → 707
- live 验证：cron + heartbeat 各连续触发 ≥2 次

## 测试策略

- 后端回归：`pytest tests/unit/personal_assistant/test_cron_scheduler.py tests/unit/personal_assistant/test_heartbeat_scheduler.py tests/contract/`
- 全量回归：`pytest -m "not e2e"`（2513 passed，预先存在 2 个 /tmp 路径 IM 集成失败）
- Live 验证：IM + Gateway 起服务，观察直聊消息多次出现

## Roadpoints

| ID | Title | Status |
|---|---|---|
| R1 | R6-1 ceil bug 红测试 + CRITICAL-1 合约修复 | DONE |
| R2 | R6-1 实现：floor 替换 ceil（cron+heartbeat）+ R6-2 awareness 注入修复 | DONE |
| R3 | 文档 + live 验证 | DONE |
