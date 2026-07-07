# refactor-454 - 验收报告

> 对齐: `docs/changes/refactor-454-gateway-runtime-protocol/motivation.md`

# Round 1 - 2026-07-07

## Verdict

- Verdict: fail
- Highest Required Action: fix-implementation
- Review mode: full
- Review worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-refactor-454`
- Branch reviewed: `unit/refactor-454`
- Baseline before orchestrator: `93fa249387933edd694a0a4a589dcc016d1a1112`
- Needs re-review: true

本轮没有发现 Web IM direct/group、Gateway reconnect/restart、Coding CLI 基础路径的用户可见回归；这些路径在真 IM + Gateway 栈或真实 CLI 入口下通过。

但本 unit 的 mandatory acceptance 包含 Feishu/Lark 真平台私聊、群聊、未 @ shadow、IM offline 外部主路径。当前 worktree 隔离 Gateway 配置里没有任何 `feishu:*` channel，也没有可验证的 Feishu/Lark 凭据；按 reviewer 规则，不能用 fake inbound 冒充真平台通过，因此 Feishu/shadow 相关 Scenario 全部为 `inconclusive`。另外权限审批、新建 agent 后重启仍可用、workspace mirror mismatch 的用户闭环未在本轮走完，也不能标 pass。

## User Journeys Exercised

1. Service takeover and health check
   - Ran `git fetch origin && git pull --ff-only origin unit/refactor-454`.
   - Ran `./scripts/e2e-down.sh`, then `./scripts/e2e-up.sh` with `.venv` first on `PATH`.
   - Verified `curl "$IM_URL/"` succeeds, logged in as `nano`, and `GET /im/v1/nodes` showed node `wt-unit-refactor-454-61647` as `online` with `agent_count=4`.
   - Note: in this Codex execution environment, child services from a one-shot shell exited when the shell ended; I reran the same runbook startup inside a keepalive shell, then cleaned it with `./scripts/e2e-down.sh`.

2. Web IM direct user-agent conversation
   - Created a direct conversation with `default-agent` through the real IM HTTP API.
   - Sent user message through `POST /im/v1/conversations/{id}/messages` with `target_node_id`.
   - Observed user message `delivery_status` change to `completed` and an agent reply from `default-agent` with content `OK.` and `delivery_status=completed`.

3. Web IM duplicate visible send observation
   - Reposted the same direct-conversation message twice with the same HTTP `Idempotency-Key`.
   - Observed two visible user messages but only one new agent reply. This is not a strict Gateway relay retry simulation, so it is recorded as a side finding instead of closing the relay retry Scenario.

4. Web IM group selection and running-state closeout
   - Created a group conversation containing user, `plato`, and `hume`.
   - Sent `@plato Reply exactly PLATO-OK.`.
   - Observed only `plato` create a running agent bubble, then close to `delivery_status=completed` with `PLATO-OK.`; `hume` remained silent.
   - Sent an ordinary unmentioned group message and observed no new agent reply after 10 seconds.

5. Coding CLI non-interactive entry
   - Ran `PYTHONPATH=src .venv/bin/python -m coding_cli.main --text "Reply exactly CLI-OK"`.
   - Observed NDJSON `assistant_message` content `CLI-OK` and final `run_status=completed`.

6. True-stack critical path e2e
   - Ran `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 pytest` for:
     - `tests/e2e/critical_paths/test_tool_call_reply_critical_path.py`
     - `tests/e2e/critical_paths/test_restart_session_continuity_critical_path.py`
     - `tests/e2e/critical_paths/test_cron_push_critical_path.py`
     - `tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py`
   - Result: `4 passed in 90.32s`.
   - Ran `tests/e2e/critical_paths/test_heartbeat_bubble_critical_path.py -ra --timeout=240`.
   - Result: `1 xfailed in 185.29s`, matching tracked product bug #126. This was not used as green evidence.

7. Broad non-e2e regression safety net
   - Ran `PYTHONPATH=src .venv/bin/python -m pytest -m "not e2e" -q`.
   - Result: `3325 passed, 2 skipped, 22 deselected, 16 warnings in 129.76s`.

## Issues

### Issue 1: Feishu/Lark true-platform acceptance path was not verifiable

- Severity: blocking
- Regression Relation: unclear
- Recommended Action: fix-implementation
- Action Rationale: Feishu private chat, group @Bot, unmentioned group shadow sync, and IM-offline external-channel continuity are mandatory in `motivation.md`. The runbook explicitly requires true Feishu/Lark inbound messages, and the current isolated Gateway config has no `feishu:*` channels. No fake inbound was used, so these required Scenarios remain inconclusive.
- User-facing impact: A user who relies on Feishu/Lark cannot be protected by this acceptance round.
- Evidence: `.gateway-config.yaml` inspection reported `feishu_channels=[]`; no Feishu/Lark true-platform message was sent.
- Re-review requirement: provide a credentialed Feishu/Lark channel in the reviewer environment, or have a subsequent round run the same true-platform journeys.

## Side Findings

- Reposting the same Web IM HTTP message with the same `Idempotency-Key` produced two visible user messages but only one agent reply. This was not treated as the `relay.message` retry Scenario because it was a repeated HTTP user send, not a true Gateway relay redelivery.
- `scripts/e2e-up.sh` was usable for the worktree stack, but services did not survive a one-shot Codex shell exit in this environment. Keeping the shell alive made the same runbook path stable. All services were cleaned with `./scripts/e2e-down.sh`.
- Heartbeat active-bubble remains the tracked xfail #126 and was not counted as new pass evidence for this unit.

## Acceptance Criteria Coverage

### Requirement: Web IM 对话与 relay 投递行为不变 - 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户在 Web IM 直聊 agent | `motivation.md` | Real IM HTTP data path plus Gateway relay, direct user-agent conversation with `default-agent` | User message became `completed`; `default-agent` replied `OK.` in same conversation with `delivery_status=completed` | pass | Used the same IM HTTP/WS backend entrypoint as the Web IM client surface allowed by design runbook. |
| 重复 relay 不产生重复用户消息 | `motivation.md` | Attempted a visible duplicate send observation via repeated HTTP message POST with same `Idempotency-Key`; also relied on non-e2e regression safety net for relay internals | Two visible user messages were created by repeated HTTP POST, one agent reply appeared | inconclusive | This was not a true `relay.message` retry or reconnect redelivery, so it cannot close the Scenario. |
| Web IM group chat 的 agent 选择语义不变 | `motivation.md` | Real IM group conversation with `plato` and `hume`, sent `@plato`, then sent an unmentioned group message | `plato` running bubble closed to `PLATO-OK.`; no `hume` reply; ordinary unmentioned message produced no new agent reply | pass | Ordinary message remained a user-visible sent message with no agent trigger, matching silent non-trigger behavior. |

### Requirement: Gateway/IM 连接、重连和节点状态表现不变 - 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Gateway 启动后节点在线 | `motivation.md`, `design.md` Runbook for Reviewer | `./scripts/e2e-up.sh`, login, `GET /im/v1/nodes` | Node `wt-unit-refactor-454-61647` status `online`, `agent_count=4`, `relay_enabled=true` | pass | Worktree isolated port and generated JWT secret were used. |
| IM 瞬断后 Gateway 自动恢复 | `motivation.md` | True-stack critical path e2e | `tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py` passed as part of `4 passed in 90.32s` | pass | Covers IM restart/reconnect and Gateway-starts-before-IM recovery to node online. |
| Gateway 重启后会话续接 | `motivation.md` | True-stack critical path e2e | `tests/e2e/critical_paths/test_restart_session_continuity_critical_path.py` passed as part of `4 passed in 90.32s` | pass | User-visible continuity covered by the critical path. |

### Requirement: workspace_root 相关用户行为不变 - 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 本地 runtime 工作区不被 IM mirror 改变 | `motivation.md` | Startup agent listing plus non-e2e regression safety net | `GET /im/v1/agents` showed runtime workspaces under `.gateway-workspace/<agent>`; `pytest -m "not e2e"` passed | inconclusive | I did not complete a user-visible mismatch journey where IM mirror workspace is deliberately changed and agent file behavior proves local-wins. |
| 用户在 IM 新建 agent 后可立即使用 | `motivation.md` | Not run | N/A | inconclusive | The HTTP API for node-agent creation was visible, but I did not create a new agent, chat with it, and restart Gateway in this round. |

### Requirement: 外部 channel 与 shadow 会话行为不变 - 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Feishu 私聊同步到内部 IM shadow 会话 | `motivation.md`, `docs/operator-runbook.md` | Required true Feishu/Lark 1:1 message | `feishu_channels=[]` in isolated Gateway config | inconclusive | No fake inbound used. |
| Feishu 群聊 @Bot 触发回复 | `motivation.md`, `docs/operator-runbook.md` | Required true Feishu/Lark group @Bot message | `feishu_channels=[]` in isolated Gateway config | inconclusive | No fake inbound used. |
| Feishu 群聊未 @ 消息只同步上下文 | `motivation.md`, `docs/operator-runbook.md` | Required true Feishu/Lark group non-mention message | `feishu_channels=[]` in isolated Gateway config | inconclusive | No fake inbound used. |
| IM 离线时 Feishu 主路径不受影响 | `motivation.md`, `docs/operator-runbook.md` | Required true Feishu/Lark message while IM is unavailable | `feishu_channels=[]` in isolated Gateway config | inconclusive | No fake inbound used. |

### Requirement: 运行态、终态和恢复表现不变 - 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| agent 回复运行态正常收口 | `motivation.md` | Real group `@plato` journey plus true-stack e2e | Running bubble for `plato` closed to `completed` with `PLATO-OK.`; critical e2e passed | pass | No permanent running bubble observed in the covered path. |
| 工具调用状态正常收口 | `motivation.md` | True-stack critical path e2e | `tests/e2e/critical_paths/test_tool_call_reply_critical_path.py` passed as part of `4 passed in 90.32s` | pass | Tool-call visible reply path covered by e2e. |
| 权限等待与审批结果不变 | `motivation.md` | Not run | N/A | inconclusive | No real approval card allow/reject journey was exercised. |
| 后台任务完成回复回到原会话 | `motivation.md` | Cron owner-direct critical path e2e, but not a user-started background task journey | `tests/e2e/critical_paths/test_cron_push_critical_path.py` passed as part of `4 passed in 90.32s` | inconclusive | Cron push proves proactive owner-direct delivery, but does not fully prove a user-triggered background task returns to its original conversation. |

### Requirement: 本 unit 不引入新的用户能力或入口变化 - 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户入口保持一致 | `motivation.md`, `README.md`, `docs/operator-runbook.md` | Ran documented Gateway/IM runbook, Web IM HTTP data path, and Coding CLI `--text` | Node online, Web IM direct/group messages worked, CLI returned `CLI-OK` and `run_status=completed` | pass | No new user-facing entrypoint was required in covered paths. |
| 内部结构变化不暴露给用户 | `motivation.md` | Covered Web IM/Gateway/CLI paths plus broad regression | Web IM/Gateway/CLI paths behaved normally; `pytest -m "not e2e"` passed | pass | Feishu and some edge paths remain inconclusive above; within covered paths, no internal protocol detail was visible. |

## Verification Commands

```bash
git fetch origin
git pull --ff-only origin unit/refactor-454
env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-down.sh
env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-up.sh
curl -fsS "$IM_URL/" >/dev/null
curl -fsS -X POST "$IM_URL/im/v1/auth/login" ...
curl -fsS -H "Authorization: Bearer $TOKEN" "$IM_URL/im/v1/nodes"
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m coding_cli.main --text "Reply exactly CLI-OK"
env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/unit-refactor-454/src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/e2e/critical_paths/test_tool_call_reply_critical_path.py tests/e2e/critical_paths/test_restart_session_continuity_critical_path.py tests/e2e/critical_paths/test_cron_push_critical_path.py tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py -ra
env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/unit-refactor-454/src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/e2e/critical_paths/test_heartbeat_bubble_critical_path.py -ra --timeout=240
env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/unit-refactor-454/src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m "not e2e" -q
env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-down.sh
```

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。本 unit 是 internal refactor，当前跨包边界仍是 IM / Gateway / CLI / agent.sdk。
- [x] `docs/specs/gateway/spec.md`（长青行为契约层，本 unit 触及 Gateway）：无需更新。本 unit declares `no spec delta`;本轮没有发现需要新增用户契约的行为。
- [x] `docs/specs/im/spec.md`（长青行为契约层，本 unit 触及 IM）：无需更新。本 unit declares `no spec delta`;本轮没有发现 IM 用户契约新增。
- [x] `docs/specs/cli/spec.md`（长青行为契约层，本 unit 间接受 CLI smoke）：无需更新。CLI `--text` 行为保持既有入口。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。现有 worktree isolated service guidance was sufficient.
- [x] `docs/SPEC_GUIDE.md`（文档规范，仅当本 unit 改了文档体系本身时）：无需更新。

## Recommended Next Step

Do not accept `refactor-454` from this round as fully passed. Re-run reviewer acceptance with a real Feishu/Lark channel configured, and close the remaining inconclusive user journeys: true relay redelivery, workspace mirror mismatch local-wins, IM-created agent persistence after Gateway restart, permission approval allow/reject, and user-started background task completion routing.
