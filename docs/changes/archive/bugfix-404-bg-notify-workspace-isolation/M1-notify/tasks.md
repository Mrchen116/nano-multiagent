# bugfix-404-M1 tasks: kernel 后台通知修复

## 目标

修复 PA 下后台任务完成通知丢失（#8）：
- `BackgroundTaskRecord` 补 `workspace_root` 字段，注册时捕获，投递时透传
- `_deliver_notification` 删除裸 `except ValueError: pass`，改为显式判断子 session 并给出可观察的错误日志
- bash/agent 工具注册时从 `ctx.repo_root` 取 session workspace 传入

## 退出标准

- `[worker]` 回归测试：非默认 workspace_root 下 bash + subagent 完成通知送达 parent session（修前红）
- `[worker]` 子 session 的后台任务完成不起顶层 run（跳过语义保留，测试覆盖）
- `[worker]` 前台 budget 内完成仍不发通知（#19 不回归）
- `[worker]` 投递失败路径产生 log_error（测试断言日志）
- `[worker]` `pytest tests/ -m "not e2e"` 全绿

## 测试策略

这是纯后端/内核修复，无前端变更。
- 测试策略：在现有 `tests/unit/agent/background_tasks/test_platform_adapters.py` 补充通知投递测试
- 核心断言：带非默认 workspace_root 的 bash/subagent 任务完成后，runs_registry.submit 能以正确参数被调用
- 子 session 跳过：parent_session_id 有 parent 链的 session 不触发 submit
- log_error 可观察：submit 抛出非 ValueError（如 session 不存在）时断言 log_error 被调用

## Frontend State Matrix

N/A — 纯内核修复，无前端变更

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | BackgroundTaskRecord 补 workspace_root 字段 + registry 签名 | DONE |
| R2 | bash/agent 工具注册调用传 workspace_root | DONE |
| R3 | _deliver_notification：删裸 except pass，显式判断子 session，透传 workspace_root | DONE |
