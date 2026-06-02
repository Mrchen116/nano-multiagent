# feat-394-M2: cron-subsystem — Progress

Worktree: /Users/czj/Repos/nano-multiagent/.worktrees/feat-394-M2
Branch: milestone/feat-394-M2
Unit branch: unit/feat-394

## 基线

测试基线（2026-06-02）：2383 通过，2 跳过，2 个 macOS /tmp vs /private/tmp 路径问题为预存失败（issue #75，非本 unit 引入）。

## M1 地基复用清单

- `_AtSchedule`/`_IntervalSchedule`/`_CronSchedule`：M1 已改为不补跑语义（openclaw computeNextRunAtMs），R1 直接为 cron job 子系统写专属单测
- `AgentWorkspaceConfig.heartbeat_enabled`：R4 仿照此字段模式新增 `cron_enabled`
- `heartbeat_json` IM→gateway 同步链路：R4 仿照新增 `cron_json`/`cron_enabled` 同款流程
- `_heartbeat_enabled(ctx)` enabled_when 机制：R8 仿照新增 `_cron_enabled(ctx)` 和 `_both_enabled(ctx)` 路由门控
- feat-393 投递闭环（node.streaming_delta + turn_start{to_user_id} + canonical 直聊）：R5 复用
- `PersistentSessionBindingStore.find_direct_by_agent`：R5 用来找 owner canonical 直聊 kernel session 以注入 System(untrusted)

---

<!-- Roadpoint 记录将在每个 R 完成后追加 -->
