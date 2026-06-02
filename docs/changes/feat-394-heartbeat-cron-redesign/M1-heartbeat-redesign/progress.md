# feat-394-M1: heartbeat-redesign — Progress

Worktree: /Users/czj/Repos/nano-multiagent/.worktrees/feat-394-M1
Branch: milestone/feat-394-M1
Unit branch: unit/feat-394

## 基线

测试基线（2026-06-02）：2349/2350 通过，1 个 macOS /tmp vs /private/tmp 路径问题为预存失败（feat-393 带入，非本 unit 引入，issue #75）。

---

### R1 — _IntervalSchedule/_CronSchedule 不补跑语义

- Context: feat-393 fix-r2 实现的是"折叠到最近一次"补跑，design 决策3/4 要求改为 openclaw 完全不补跑（只等下一个未来时隙）
- Decision:
  - `_IntervalSchedule`: steps = ceil(elapsed/interval)，next = anchor + steps * interval，若 next > now 则不触发
  - `_CronSchedule`: 只检查当前分钟是否匹配 + 未在同一分钟触发过（dedup guard），不遍历历史
- Rationale: 与 openclaw computeNextRunAtMs 语义对齐；重启后不补跑历史是用户明确要求（spec "重启不刷屏"）
- Evidence:
  - Tests: 9/9 passed (test_heartbeat_scheduler.py); 2347 passed 全套
  - Entry: 单元测试；N/A（非入口变更）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（调度器纯逻辑）
  - Visual/Interaction: N/A
- Rollback: 50d14e81 (C1 红测试)
- Commits: C1=50d14e81, C2=aee9b0a7
- Next: R2 — AgentWorkspaceConfig heartbeat 字段 + 调度器 per-agent 开关过滤
