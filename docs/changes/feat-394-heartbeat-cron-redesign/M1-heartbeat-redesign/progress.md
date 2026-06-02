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
- Next: R2 完成，进入 R3

### R2 — AgentWorkspaceConfig heartbeat 字段 + 调度器 per-agent 开关过滤

- Context: 需要 per-agent heartbeat_enabled 门控调度器；同时新增 heartbeat_every/active_hours 字段备 R6/R7 使用
- Decision:
  - `AgentWorkspaceConfig` 新增 `heartbeat_enabled(bool)`, `heartbeat_every(str|None)`, `heartbeat_active_hours_{start,end,timezone}(str|None)` 字段
  - `HeartbeatScheduler.tick()` 在读 HEARTBEAT.md 前先检查 `agent.heartbeat_enabled`，False → 直接 skip
  - `_parse_agents()` 解析 YAML `heartbeat:` 块；`save_local_config()` 序列化（仅在有非默认值时才写出）
- Rationale: 开关必须在 IM 配置 → gateway sync 路径完整落地前，先建好数据模型
- Evidence:
  - Tests: 12+3=15/15 passed (test_heartbeat_scheduler); 2350 全套通过
  - Entry: 单元测试；N/A（配置解析，非入口变更）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 0aaec6d9 (C1 红测试)
- Commits: C1=0aaec6d9, C2=49375325
- Next: R3 — HEARTBEAT_OK 静默 + 空文件跳过 + prompt 段照抄 openclaw
