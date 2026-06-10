# M6-fix-round4 Tasks

## 目标

修复 round-4 验收 2 个 issue，使 cron job 能真实到点触发并把结果投递进直聊。

退出标准：
1. R4-1 (blocking): cron_runner `create_session` 调用签名对齐 `_KernelClientShim`，cron job 到点触发后不再 TypeError crash，结果消息出现在 IM 直聊。
2. R4-2 (major): 判定为 env 问题——主 config 有 user_id，e2e 起 gateway 时 user_id 写入 config，heartbeat 能正常投递；e2e 验证投递成功（非 owner_unresolved）。
3. 补 durable 集成测试：cron run 路径走真实 `_KernelClientShim`（非 stub），堵住层间契约不符的复发。
4. 全套回归 pytest -m "not e2e"（含 im_service）+ tsc -b + vitest 全绿。

## 测试策略

- R1: 写红测试验证 cron_runner 调用真实 shim 时无 TypeError，测试不允许传 session_id 给 shim
- 修复: 删除 cron_runner._submit_cron_job 中的 `session_id=` 参数，更新 _KernelClientLike Protocol 对齐真实 shim
- E2E 验证: 起 IM + gateway，启用 cron，向 agent 注册 30s cron job，等待触发，确认消息投递进直聊

## Roadpoints

| id | title | status |
|---|---|---|
| R1 | 红测试 — cron_runner 调用真实 shim create_session 无 TypeError | DONE |
| R2 | 修复 cron_runner create_session 契约不符 | DONE |
| R3 | E2E 验证：cron tick 路径正确 + heartbeat delivery 环境确认 | DONE |
| R4 | 文档收口 | DONE |
