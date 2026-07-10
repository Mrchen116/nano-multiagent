# bugfix-383-M1: watchdog-idle-signal

## 目标

把 watchdog 判活信号从 `messages.created_at` 改为"最近 event 时间"，阈值 300s→120s，更新失败文案。
正在活跃推 event 的长 relay 不再被误杀。

## 退出标准

- (a) `pytest tests/im_service/unit/test_relay_watchdog.py` 全绿
- (b) `pytest tests/im_service` 无连带回归
- (c) 手工长 tool 循环不再误杀 [reviewer 验]
- (d) `IM_RELAY_WATCHDOG_TIMEOUT_SECONDS` env override 仍生效（日志能看到自定义值）[worker]

## 测试策略

后端纯逻辑变更，用单元测试覆盖全部路径。不做前端改动。

**新增测试用例（R1/C1 写失败测试）：**

1. `test_active_relay_not_killed` — message 10 分钟前创建，但 conversation_events 30 秒前刚 append `tool_call.upserted` → 返回 0，message 仍 running
2. `test_idle_relay_killed` — message 10 分钟前创建，最后 event 5 分钟前 → 返回 1，flip 到 failed，content 含新文案 "relay idle for 120s..."
3. `test_no_event_fallback_to_created_at` — message 4 分钟前创建，零 event → fallback 到 created_at，被杀（> 120s）
4. `test_boundary_just_over_timeout` — last_evt 121s 前 → 被杀
5. `test_boundary_just_under_timeout` — last_evt 119s 前 → 不被杀

**现有文案断言需更新（R2/C2 同步改）：**
- `test_scan_writes_detail_into_empty_message_content` 的 content 断言
- `test_scan_appends_error_note_to_partial_streamed_content` 的 content 断言

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 写新增失败测试（RED） | DONE |
| R2 | 实现 SQL 改造 + default 120s + 文案更新 + 修文案断言（GREEN） | DONE |
| R3 | 验证 env override，补文档 | DONE |
