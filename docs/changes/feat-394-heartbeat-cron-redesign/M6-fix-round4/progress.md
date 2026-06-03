# M6-fix-round4 Progress

## 背景

Round-4 验收 fail，2 个 issue：
- R4-1 (blocking): cron_runner.py:92 传 `session_id=` 给 `_KernelClientShim.create_session`，但 shim 无此参数 → TypeError crash
- R4-2 (major): heartbeat delivery skipped `owner_unresolved`

判定：
- R4-1 = code bug（protocol 声明与真实 shim 不符）
- R4-2 = env 问题（reviewer worktree config.node.user_id 未绑定；主 config 有 user_id，e2e 验证会确认）
