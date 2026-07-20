# refactor-470 — Round 4 Cron 更正验收报告

> 验收对象：`unit/refactor-470` @ `d5873b3879b80e3075a7d9a9358bc1a4626a818c`
>
> 复验范围：纠正 Round 3 对启动职责 delta 中 Cron 主动消息旅程的无效环境结论；其余 Round 3 targeted 结论按原证据继承。

## Verdict

**pass-with-issues**

**Highest Required Action：out-of-unit**

Round 3 的 Cron `fail` 已作废：当时没有使用 M4 已验证的、含测试固定模型 `kimiCoding:K2.6` 的 worktree-local 路由配置，超时不能归因于产品。以同一已验证前置重新运行隔离真栈后，用户收到了 Cron 主动消息，旅程通过。Gateway/IM 中断恢复、重启后会话连续性，以及 Fix R1 的 Feishu online/offline durable evidence 均保持通过。

唯一保留事项是既有 heartbeat #126；它是 Round 1 已记录的 `unrelated-existing` / `out-of-unit` 问题，不是本次启动职责 delta 的回归。

## Correction of Round 3

Round 3 在 `b52362df0` 使用默认 source config 运行 Cron 旅程，未提供已验证的固定模型路由，因而等待用户可见回复时超时。该条件与 `M4-composition-root-closure/progress.md` 第 103–110 行记录的成功环境不一致，不能证明 Cron 启动或投递失败。

本轮从用户持久配置派生临时 `HOME`，仅在副本的同一 `anthropic` provider 中补入 `kimiCoding:K2.6` 模型条目；未修改用户持久配置、源码或测试。运行结束后该临时 HOME 已删除。

## User Journeys Exercised

1. **Cron 定时主动消息（独立更正复验）**：使用隔离 HOME、可用模型路由、真 IM 与真 Gateway 运行 `test_cron_push_critical_path.py`。用户经 IM 收到 Cron 注册后的主动哨兵消息。
2. **Gateway/IM 中断恢复（继承 Round 3）**：隔离真进程的 resilience/restart 旅程 3 项通过，耗时 39.53 秒。
3. **Gateway 重启后会话连续性（继承 Round 3）**：同一隔离真进程旅程通过，用户可在重启后继续原会话。
4. **Feishu online reconnect 与 cached offline autonomy（继承 Fix R1 durable evidence）**：不争抢共享 Bot；继承已记录的精确在线/离线消息往返。

## Reference Artifacts Reviewed

N/A。没有前端原型或视觉对齐契约。

## Issues

### 1. Heartbeat 有内容时的用户可见冒泡仍不可验证

- **Severity**：major
- **Regression Relation**：unrelated-existing
- **Recommended Action**：out-of-unit
- **Action Rationale**：继承 Round 1：`design.md` 第 444–445 行将该真链路列为既有 #126 的 strict xfail。本轮没有修改或扩展 heartbeat 行为，不能把既有问题归为本次启动职责 delta 的回归。
- **Existing issue**：#126（不重复创建 GitHub issue）。

## 验收标准覆盖

### Requirement: Managed channel 在线控制行为保持一致 — 组内结论：pass（继承）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 在线保存后无需重启即可使用 | `motivation.md` 第 58–63 行 | 继承 Fix R1 真实 Feishu reconnect 消息往返 | `M4-composition-root-closure/progress.md` Fix R1 第 125 行 | pass | 本轮不抢占共享 Bot。 |
| 无效配置不伪装成功且不影响其他 Bot | `motivation.md` 第 64–68 行 | 继承 Round 1 fixture 验证 | `acceptance-round-1.md` 第 44 行 | pass | 与本 delta 无关。 |
| 停用、删除或替换只作用于目标 channel | `motivation.md` 第 70–74 行 | 继承 Round 1 fixture 验证 | `acceptance-round-1.md` 第 45 行 | pass | 与本 delta 无关。 |

### Requirement: Managed channel 离线自治与重连收敛保持一致 — 组内结论：pass（继承）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| IM 离线重启后缓存 channel 仍可用 | `motivation.md` 第 78–82 行 | 继承 Fix R1 cached offline 真实消息往返 | `M4-composition-root-closure/progress.md` Fix R1 第 126 行 | pass | 不争抢共享 Bot。 |
| IM 恢复后收敛到最新配置 | `motivation.md` 第 84–87 行 | 继承 Round 3 隔离真 IM/Gateway resilience | `acceptance-round-3.md` 的 3 passed / 39.53s | pass | 本轮未改写该旅程结果。 |

### Requirement: Gateway 服务生命周期保持一致 — 组内结论：pass（继承）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| start、stop、restart 结果不变 | `motivation.md` 第 91–94 行 | 继承 Round 3 隔离真 Gateway 重启与会话连续性 | `acceptance-round-3.md` 的 3 passed / 39.53s | pass | 本轮没有残留隔离服务。 |
| 新节点自动绑定行为不变 | `motivation.md` 第 96–99 行 | 继承 Round 1 隔离 auto-bind 验收 | `acceptance-round-1.md` 第 59 行 | pass | 与本 delta 无关。 |

### Requirement: Heartbeat 与 Cron 主动行为保持一致 — 组内结论：pass-with-issues

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Heartbeat 有内容时冒泡、无内容时静默 | `motivation.md` 第 103–106 行；`design.md` 第 444–445 行 | 继承 Round 1 既有问题结论 | `acceptance-round-1.md` 第 65 行；#126 | inconclusive | `unrelated-existing` / `out-of-unit`，不属于本 delta。 |
| Cron 定时与手动运行保持现有语义 | `motivation.md` 第 108–111 行 | 使用隔离 HOME 的可用模型路由，运行真栈 Cron 用户旅程 | `HOME=<temporary isolated home> NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/e2e/critical_paths/test_cron_push_critical_path.py -o timeout=360 --tb=long` → `1 passed in 41.49s` | pass | 用户可见主动消息已送达；Round 3 的未配置超时由本条更正。 |

## Side Findings

- Round 3 的 Cron direct finding 已被本报告取代；不得据其派发实现修复。
- 临时 HOME/config 和该轮隔离服务均已清理；没有修改用户持久配置或保留 worktree Gateway/IM 进程。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。
- [x] `docs/specs/gateway/`（长青行为契约层）：无需更新；本轮校正的是验收环境前置，不是契约变化。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/SPEC_GUIDE.md`：无需更新。
