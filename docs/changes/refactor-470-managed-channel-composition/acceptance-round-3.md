# refactor-470 — Round 3 targeted 产品验收报告

> 验收对象：`unit/refactor-470` @ `b52362df0ba1cf3edba6fff2ea2cd4a241d9b2be`
>
> 复验范围：`0e6cee1eb..b52362df0` 中启动职责调整所直接影响的用户旅程。继承 Round 1 与 Fix R1 的未受本 delta 影响结论。

## Verdict

**fail**

**Highest Required Action：fix-implementation**

Gateway/IM 中断恢复及重启后会话连续性在隔离真 IM 与真 Gateway 进程中均通过；Fix R1 的真实 Feishu online reconnect 和 cached offline autonomy 证据可继承。可是本轮独立运行 Cron 定时主动消息旅程时，用户始终没有收到预期的 agent 回复，测试在等待用户可见消息时超时。因此，直接受本次启动时序 delta 影响的 Cron 旅程未被验证为可用，不能交付。

## User Journeys Exercised

1. **Gateway/IM 中断恢复**：在隔离端口的真 IM 与真 Gateway 进程上运行 `scripts/e2e-critical.sh -k 'gateway_im_resilience or restart_session_continuity'`。用户消息在 IM 中断恢复后仍可得到回复。
2. **Gateway 重启后会话连续性**：同一真进程旅程通过；重启后用户可继续原有会话。
3. **Cron 定时主动消息**：使用 `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1` 运行 `test_cron_push_critical_path.py`，等待用户可见 agent 消息时超时，未收到 cron 投递结果。
4. **Feishu online reconnect（继承）**：不争抢共享 Bot，继承 Fix R1 durable evidence：authenticated reconnect 后，用户在原 1:1 会话请求 `ONLINE-R1-OK-20260720-3`，收到精确同文本回复。
5. **Feishu cached offline autonomy（继承）**：继承 Fix R1 durable evidence：同一 encrypted cache/key、不可达 IM 下，用户请求 `OFFLINE-R1-OK-20260720-1`，收到精确同文本回复。

## Reference Artifacts Reviewed

N/A。`design.md` 明确本 unit 没有前端原型或视觉对齐契约。

## Issues

### 1. Cron 定时主动消息未到达用户

- **Severity**：major
- **Regression Relation**：direct
- **Recommended Action**：fix-implementation
- **Action Rationale**：本次 delta 直接调整 Gateway 的启动职责与 Cron 初始注册时机。用户侧期望是在任务到点后收到投递结果；实际独立真栈验收在等待该消息时超时。问题阻断了本次受影响的主动消息旅程，须由实现修复后复验。
- **Reproduction**：在目标 HEAD 运行 `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/e2e/critical_paths/test_cron_push_critical_path.py -o timeout=360 --tb=long`；测试在 `wait_for_agent_reply_with` 等待用户可见回复时超时。

## 验收标准覆盖

### Requirement: Managed channel 在线控制行为保持一致 — 组内结论：pass（继承）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 在线保存后无需重启即可使用 | `motivation.md` 第 58–63 行 | 继承 Fix R1 的真实 Feishu reconnect 消息往返 | `M4-composition-root-closure/progress.md` Fix R1 第 125 行：`applied/connected` 后收到 `ONLINE-R1-OK-20260720-3` | pass | 本 delta 未重新改变 online managed-channel 用户旅程；为避免共享 Bot 冲突继承 durable evidence。 |
| 无效配置不伪装成功且不影响其他 Bot | `motivation.md` 第 64–68 行 | 继承 Round 1 的可控 fixture 验证 | `acceptance-round-1.md` 第 44 行 | pass | 本 delta 未涉及此破坏性场景。 |
| 停用、删除或替换只作用于目标 channel | `motivation.md` 第 70–74 行 | 继承 Round 1 的可控 fixture 验证 | `acceptance-round-1.md` 第 45 行 | pass | 本 delta 未涉及此破坏性场景。 |

### Requirement: Managed channel 离线自治与重连收敛保持一致 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| IM 离线重启后缓存 channel 仍可用 | `motivation.md` 第 78–82 行 | 继承 Fix R1 的真实 cached offline Feishu 消息往返 | `M4-composition-root-closure/progress.md` Fix R1 第 126 行：不可达 IM 下收到 `OFFLINE-R1-OK-20260720-1` | pass | durable evidence 使用同一 encrypted cache/key，未与共享 Bot 竞争。 |
| IM 恢复后收敛到最新配置 | `motivation.md` 第 84–87 行 | 独立隔离真 IM/Gateway 中断恢复旅程 | `scripts/e2e-critical.sh -k 'gateway_im_resilience or restart_session_continuity'`：3 passed，39.53s | pass | 用户在 IM 中断恢复后仍能完成消息往返，无需手工重启 Gateway。 |

### Requirement: Gateway 服务生命周期保持一致 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| start、stop、restart 结果不变 | `motivation.md` 第 91–94 行 | 独立隔离真 Gateway 重启并继续原有会话 | `scripts/e2e-critical.sh -k 'gateway_im_resilience or restart_session_continuity'`：3 passed，39.53s | pass | 复验结束后无 worktree Gateway/IM 残留进程。 |
| 新节点自动绑定行为不变 | `motivation.md` 第 96–99 行 | 继承 Round 1 的隔离 auto-bind 旅程 | `acceptance-round-1.md` 第 59 行 | pass | 本 delta 聚焦启动职责，不改变用户可观察的 auto-bind 结果。 |

### Requirement: Heartbeat 与 Cron 主动行为保持一致 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Heartbeat 有内容时冒泡、无内容时静默 | `motivation.md` 第 103–106 行；`design.md` 第 444–445 行 | 继承 Round 1 已知结论 | `acceptance-round-1.md` 第 65 行；既有 issue #126 | inconclusive | `unrelated-existing` / `out-of-unit`，不归为本次 delta 的新回归，也不重复立 issue。 |
| Cron 定时与手动运行保持现有语义 | `motivation.md` 第 108–111 行 | 独立真栈运行 cron critical path，观察用户收到主动消息 | `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 ... test_cron_push_critical_path.py -o timeout=360 --tb=long`：等待用户可见 agent 回复时超时 | fail | 用户没有收到 cron 主动消息；不得以内部测试或函数调用替代该用户结果。 |

## Side Findings

- 既有 heartbeat #126 保持 `unrelated-existing` / `out-of-unit`，不属于本次启动职责 delta 的新增回归。
- 本轮独立启动的隔离服务均已退出；未触碰共享 Feishu Bot，也未留下 worktree IM/Gateway 进程。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。本 unit 没有对外架构 delta。
- [x] `docs/specs/gateway/`（长青行为契约层）：无需更新。Cron 本轮失败是实现回归，不能以修改契约掩盖。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/SPEC_GUIDE.md`：无需更新。
