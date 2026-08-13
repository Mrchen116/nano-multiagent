# bugfix-536 — 回归验证

> 对齐: incident.md
>
> Validation snapshot: `84b386b42 → 5d8a6dea3`
>
> Review round: 1 (`full`)

## Verdict

- **Verdict**: `fail`
- **Highest Required Action**: `fix-implementation`
- 事故主路（自动压缩期间追加、真中断后一次可见接管、后续继续聊天、common Gateway 外部投递语义）本轮未再现原故障。
- 但明确要求保持不变的精确 `/new` 发出“已开始新会话”后，下一条消息仍能读出旧会话口令；两个独立聊天稳定复现，因此第 1 轮不能通过。

## Reference Artifacts Reviewed

- 无原型、设计稿或视觉 must-match 契约；本轮以 `incident.md` 的 Requirement/Scenario、`design.md` 的 Reviewer Runbook 和真实 Web IM 时间线为验收真值。

## User Journeys Exercised

1. **自动压缩中追加消息**：在隔离 Web IM 直聊写入约 240,000 个 token 的长上下文，1 秒后追加普通消息，观察整理期间状态、最终回复次数与上下文。
2. **真中断后可见接管**：运行真实 Kernel + common Gateway coordinator 的确定性恢复集成旅程，在 predecessor 已接收但未消费补充消息时中断，验证无需重发且只交付一次。
3. **同一聊天继续与 common delivery**：在压缩续聊完成后继续发消息，再核外部 ingress 首次 ACK 与 recovery adoption 不产生第二次 ACK/sent receipt。按派发约束未连接真实飞书租户。
4. **控制词边界**：同一聊天依次验证非精确 `/stop` 、非精确 `/new` 作为普通消息并保留口令；精确 `/stop` 停止正在进行的静默等待；精确 `/new` 后检查旧口令是否隔离，并在新聊天重复一次。

## 验收标准覆盖

### Requirement: 聊天中追加的消息在活跃但安静的阶段仍正常继续

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 自动压缩期间追加消息 | `incident.md` 目标状态与 Scenario | 隔离 IM + Gateway 真栈，Web IM 客户端使用的 REST relay 入口 | conversation `ad42c1e59b934e588dde95875834167d`；root `fadbec...` 与 supplement `ed5fdb...` 均 `completed`；36.073s 静默阶段无 failed；最终仅一条非空回复 `CTX-536 压缩续聊通过`；`cache_total_input_tokens=251669` 后 `context_used=6389` | `pass` | 旧 provisional 气泡空正文 `completed`，没有向用户误报失败；补充回复同时带回压缩前标记。 |

### Requirement: 真正中断后，已接收的后续消息仍有一次可见的继续结果

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 中断前已接收补充消息 | `incident.md` 目标状态与 Scenario | 真实 Kernel + common Gateway coordinator 的确定性中断/恢复集成旅程；另跑 external recovery no-second-ACK 投递契约 | `test_real_kernel_recovery_handoff_delivers_accepted_follower_once` 1 passed；`test_correlated_successor_delivers_once_and_terminalizes_all_followers` 1 passed；`test_recovery_adopted_seeds_context_without_second_ack_or_sent_receipt` 1 passed | `pass` | 确定性旅程强制 predecessor 在已接收、未消费普通消息后终止；真飞书生产 tenant 明确排除。 |
| 中断后的下一条正常消息 | `incident.md` 目标状态与 Scenario | adopted successor 期间再发普通消息；真栈压缩续聊后再发一条消息 | `test_new_message_during_adopted_successor_stays_same_run` 1 passed；conversation `ad42c1...` 随后回复 `CTX-536`，message `0afb8e...` `completed` | `pass` | 后续消息无需重建聊天，且保留前序上下文。 |

### Requirement: 所有 Gateway 聊天入口体验一致

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 从不同入口继续同一聊天 | `incident.md` 目标状态与 Scenario；派发约束“common Gateway 入口，不访问真飞书生产 tenant” | Web IM 真栈 + common runtime-delivery 外部 ingress 契约 | Web IM conversation `ad42c1...` 正常可见；`test_relay_lifecycle_accepted_acks_feishu_message_processing_started` 1 passed；recovery adopted no-second-ACK/no-second-receipt 1 passed | `pass` | 没有连接或修改真实飞书生产租户；飞书与其他外部 channel 只核 common delivery seam 的用户可见语义。 |

## 复现验证

1. 修复后在 Web IM 真栈造出 251,669 input-token 级的自动整理，立即发补充消息。安静阶段持续约 36 秒，root/supplement 均未进入 failed，不再出现“追加消息无回应/超时”。
2. 整理后交付的唯一非空 Agent 回复是 `CTX-536 压缩续聊通过`，同时证明新补充和压缩前上下文均进入后续对话。
3. 真中断窗口通过确定性 common Gateway 集成旅程强制触发；accepted follower 不需重发，终态化一次，最终文本交付一次。

## 回归测试

- 非精确 `/stop now，...` 是普通消息，Agent 正常回复旧上下文口令 `青松-536`。
- 非精确 `/new please，...` 是普通消息，Agent 正常回复旧上下文口令 `青松-536`。
- 精确 `/stop` 在一条 30 秒静默等待运行中返回 `已停止当前操作。`，被停止气泡没有迟到正文。
- 精确 `/new` 确认文案正常，但旧上下文未隔离；详见 Issue 1。

## Automated Tests Exercised

- `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q -s tests/integration/test_session_run_coordinator_recovery.py::test_real_kernel_recovery_handoff_delivers_accepted_follower_once` — `1 passed in 2.74s`。
- `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q -s tests/unit/personal_assistant/test_gateway_relay_lifecycle.py::test_recovery_adopted_seeds_context_without_second_ack_or_sent_receipt tests/unit/personal_assistant/test_gateway_relay_lifecycle.py::test_relay_lifecycle_accepted_acks_feishu_message_processing_started` — `2 passed in 0.99s`。
- `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q -s tests/unit/personal_assistant/test_recovery_handoff_coordinator.py::test_correlated_successor_delivers_once_and_terminalizes_all_followers tests/unit/personal_assistant/test_recovery_handoff_coordinator.py::test_new_message_during_adopted_successor_stays_same_run` — `2 passed in 0.67s`。

## Issues

### 1. 精确 `/new` 确认开始新会话后仍泄漏旧上下文

- **Severity**: `major`
- **Regression Relation**: `direct`
- **Recommended Action**: `fix-implementation`
- **Action Rationale**: 本 unit 明确要求精确 `/new` 维持“重开且不带旧上下文”的既有用户契约；确认文案与实际上下文相互矛盾，属于实现修复。
- **Expected**: 用户发送精确 `/new` 并看到“已开始新会话”后，后续普通消息不带旧会话上下文。
- **Actual**: 第一个聊天在 `/new` 后准确回答 `口令：青松-536`；第二个全新聊天重复后准确回答 `白鹤-536`。
- **Reproduction**:
  1. 在 Web IM 直聊发送“记住口令：白鹤-536”，等 Agent 确认。
  2. 发送精确 `/new`，看到 `已开始新会话。`。
  3. 发送“如果当前上下文不知道上一会话口令，只回复不知道；否则回复口令”。
  4. Agent 回复 `白鹤-536`。
- **Evidence**: conversation `00697dfa3f9e4849aa92dda6a1112a2a`；`/new` message `2114db...`；confirmation `d5762e...`；post-new reply `4b152a...`。独立 conversation `31474a11487c4ee6afc3f6e7397d4d42` 以 `青松-536` 第二次复现。

## Side Findings

- 无。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**；包边界和部署拓扑未变。
- [x] `docs/specs/<包>/`（长青行为契约层）：**需要更新**；需把自动压缩 liveness、非用户中断后已接收普通消息的一次可见恢复，以及 common delivery 不重复 ACK/receipt 的增量归并到 `docs/specs/kernel/runs.md`、`docs/specs/gateway/routing-delivery.md`、`docs/specs/im/gateway-relay.md`。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**；开发路由与架构红线未变。
- [x] `docs/specs/CONTRIBUTING.md`（文档规范）：**无需更新**；本 unit 没有修改文档体系。

