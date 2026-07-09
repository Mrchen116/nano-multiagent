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

---

# Round 2 - 2026-07-07

## Verdict

- Verdict: fail
- Highest Required Action: fix-implementation
- Review mode: targeted revalidation of Round 1 open items
- Review worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-refactor-454`
- Branch reviewed: `unit/refactor-454`
- Fix delta range: `1d1cec26..9ac488b1`
- Head reviewed: `9ac488b1`
- Needs re-review: true

Targeted revalidation closed the Round 1 gaps for workspace local-wins, IM-created agent critical path, permission approval allow/reject, and user-started background completion routing. The worktree isolated IM + Gateway stack was restarted from the design runbook and was online at `IM_URL=http://127.0.0.1:64019`, node `wt-unit-refactor-454-6800`, with `relay_enabled=true` and `last_error=null`.

The unit still cannot be accepted because Feishu/Lark true-platform acceptance remains unverified: both the main local config and worktree Gateway config expose only `web_relay`, with no `feishu:*` or Lark channel. No fake inbound was used. True relay redelivery also remains inconclusive from a product-review standpoint: supporting dedup tests pass, but this round still did not produce a real same-relay-frame reconnect/redelivery journey through the user-visible stack.

## User Journeys Exercised

1. Service takeover and health check
   - Ran `git fetch origin && git pull --ff-only origin unit/refactor-454` before review; worktree was already at `9ac488b1`.
   - Ran `./scripts/e2e-down.sh`, then kept a shell alive while running `./scripts/e2e-up.sh`.
   - Verified `curl "$IM_URL/"` succeeds, logged in as `nano`, and `GET /im/v1/nodes` showed node `wt-unit-refactor-454-6800` online.

2. Feishu/Lark credentialed channel check
   - Inspected only redacted channel summaries from `~/.nano-assistant/config.yaml` and `.gateway-config.yaml`.
   - Both configs had exactly one channel: `name=web_relay`, no settings keys. No `feishu:*` or Lark channel was available.
   - Result: Feishu private chat, group @Bot, non-mention shadow sync, and IM-offline Feishu main path were not run.

3. IM-created agent, permission approval, and background notification critical paths
   - Ran:

```bash
env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH \
  NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 \
  PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/unit-refactor-454/src \
  /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest \
  tests/e2e/critical_paths/test_create_agent_via_im_critical_path.py \
  tests/e2e/critical_paths/test_permission_approval_critical_path.py \
  tests/e2e/critical_paths/test_bash_background_notify_critical_path.py -ra
```

   - Result: `4 passed in 78.48s`.
   - This closes the Round 1 inconclusive items for "user creates new agent in IM, can chat, Gateway restart preserves it", permission approval allow/reject, and user-started background task completion returning to the original conversation.

4. Workspace mirror mismatch local-wins journey
   - Via public config API, attempted to patch `default-agent` with fake `workspace_root=/tmp/refactor454-im-mirror-should-not-win-1783415777`.
   - Response was `HTTP 200`, but readback still returned `/Users/czj/Repos/nano-multiagent/.worktrees/unit-refactor-454/.gateway-workspace/default-agent`.
   - `GET /im/v1/agents/default-agent/heartbeat-md` returned the local worktree `HEARTBEAT.md` content beginning with `# HEARTBEAT`, proving the visible heartbeat preview still reads the Gateway local workspace rather than the fake mirror path.
   - Supporting regression command: `pytest tests/unit/personal_assistant/test_gateway_im_config_sync.py tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py -q` -> `21 passed, 2 warnings in 2.72s`.

5. Relay duplicate / redelivery check
   - Supporting regression command: `pytest tests/unit/personal_assistant/test_gateway_relay_dedup.py tests/unit/test_runtime_retry_no_duplicate_user_message.py -q` -> `6 passed in 0.09s`.
   - This is useful safety net evidence, but it is not a true user-visible same relay frame redelivery/reconnect journey. I did not mark the Scenario pass from this evidence alone.

## Issues

### Issue 1: Feishu/Lark true-platform acceptance path is still not verifiable

- Severity: blocking
- Regression Relation: unclear
- Recommended Action: fix-implementation
- Action Rationale: Feishu private chat, group @Bot, non-mention shadow sync, and IM-offline external-channel continuity remain mandatory acceptance scenarios. The design runbook requires true Feishu/Lark inbound messages. Current main and worktree configs contain only `web_relay`; no credentialed true-platform channel was available, and no fake inbound was used.
- User-facing impact: Feishu/Lark users still have no acceptance evidence for this refactor round.
- Evidence: redacted config summaries for both `~/.nano-assistant/config.yaml` and `.gateway-config.yaml` showed only `web_relay`.
- Re-review requirement: rerun these scenarios with a credentialed Feishu/Lark channel and real private/group inbound messages.

### Issue 2: True relay redelivery remains product-review inconclusive

- Severity: major
- Regression Relation: unclear
- Recommended Action: fix-implementation
- Action Rationale: Unit-level relay dedup tests passed, but this review still did not exercise the user-visible condition "same logical relay frame redelivered after retry/reconnect" through the live IM + Gateway stack. I did not use repeated HTTP user sends as a substitute because Round 1 already showed that is not the same journey.
- User-facing impact: The review still cannot independently prove that retry/redelivery will never create duplicate visible user or agent messages.
- Evidence: `test_gateway_relay_dedup.py` and `test_runtime_retry_no_duplicate_user_message.py` passed; no true live redelivery reproduction was available from documented user/API entrypoints.
- Re-review requirement: provide a reviewer-runbook way to force or observe one unacked `relay.message` being delivered twice through the live stack, or explicitly reclassify this Scenario as non-reviewer-testable and owned by verifier tests.

## Acceptance Criteria Coverage - Round 2 Updates

### Requirement: Web IM 对话与 relay 投递行为不变 - 组内结论: fail

| Scenario | 期望来源 | Round 2 验证方式 | Round 2 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 重复 relay 不产生重复用户消息 | `motivation.md` | Supporting regression tests only; no live same-relay-frame redelivery journey | `test_gateway_relay_dedup.py` + `test_runtime_retry_no_duplicate_user_message.py` -> `6 passed` | inconclusive | Still not closed by product-review evidence. |

### Requirement: workspace_root 相关用户行为不变 - 组内结论: pass

| Scenario | 期望来源 | Round 2 验证方式 | Round 2 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 本地 runtime 工作区不被 IM mirror 改变 | `motivation.md`, `docs/specs/gateway/spec.md` | Public config API attempted fake workspace update, then heartbeat preview readback | Fake `workspace_root` was ignored; heartbeat preview returned local `HEARTBEAT.md` content; local-wins tests -> `21 passed` | pass | No direct DB patch or fake legacy state was used. |
| 用户在 IM 新建 agent 后可立即使用 | `motivation.md`, `docs/specs/im/spec.md` | Critical path e2e through IM create-agent journey | Included in `4 passed in 78.48s` | pass | Covers create, chat, and Gateway restart preservation. |

### Requirement: 外部 channel 与 shadow 会话行为不变 - 组内结论: fail

| Scenario | 期望来源 | Round 2 验证方式 | Round 2 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Feishu 私聊同步到内部 IM shadow 会话 | `motivation.md`, `docs/operator-runbook.md` | Required true Feishu/Lark 1:1 message | Main/worktree configs had only `web_relay` | inconclusive | No fake inbound used. |
| Feishu 群聊 @Bot 触发回复 | `motivation.md`, `docs/operator-runbook.md` | Required true Feishu/Lark group @Bot message | Main/worktree configs had only `web_relay` | inconclusive | No fake inbound used. |
| Feishu 群聊未 @ 消息只同步上下文 | `motivation.md`, `docs/operator-runbook.md` | Required true Feishu/Lark non-mention group message | Main/worktree configs had only `web_relay` | inconclusive | No fake inbound used. |
| IM 离线时 Feishu 主路径不受影响 | `motivation.md`, `docs/operator-runbook.md` | Required true Feishu/Lark message while IM unavailable | Main/worktree configs had only `web_relay` | inconclusive | No fake inbound used. |

### Requirement: 运行态、终态和恢复表现不变 - 组内结论: pass for targeted Round 2 rows

| Scenario | 期望来源 | Round 2 验证方式 | Round 2 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 权限等待与审批结果不变 | `motivation.md`, `docs/specs/gateway/spec.md` | Critical path e2e covering permission approval allow/reject | Included in `4 passed in 78.48s` | pass | Covers allow and reject outcomes. |
| 后台任务完成回复回到原会话 | `motivation.md`, `docs/specs/gateway/spec.md` | Critical path e2e for bash background notify | Included in `4 passed in 78.48s` | pass | Covers user-started background completion notification. |

## Verification Commands

```bash
git fetch origin
git pull --ff-only origin unit/refactor-454
env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-down.sh
env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-up.sh
curl -fsS "$IM_URL/" >/dev/null
curl -fsS -H "Authorization: Bearer $TOKEN" "$IM_URL/im/v1/nodes"
yq -o=json '.channels[] | {"name": .name, "enabled": .enabled, "setting_keys": ((.settings // {}) | keys)}' ~/.nano-assistant/config.yaml
yq -o=json '.channels[] | {"name": .name, "enabled": .enabled, "setting_keys": ((.settings // {}) | keys)}' .gateway-config.yaml
env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/unit-refactor-454/src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/e2e/critical_paths/test_create_agent_via_im_critical_path.py tests/e2e/critical_paths/test_permission_approval_critical_path.py tests/e2e/critical_paths/test_bash_background_notify_critical_path.py -ra
env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/unit-refactor-454/src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/personal_assistant/test_gateway_im_config_sync.py tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py -q
env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/unit-refactor-454/src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/personal_assistant/test_gateway_relay_dedup.py tests/unit/test_runtime_retry_no_duplicate_user_message.py -q
```

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。本轮复验没有发现跨包架构契约新增。
- [x] `docs/specs/gateway/spec.md`（Gateway 长青行为契约层）：无需更新。Round 2 复验仍按现有 Gateway 契约判断。
- [x] `docs/specs/im/spec.md`（IM 长青行为契约层）：无需更新。Round 2 复验仍按现有 IM 契约判断。
- [x] `docs/specs/cli/spec.md`：无需更新。本轮未触及 CLI 用户契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。现有 worktree e2e/runbook guidance 足够启动隔离栈。
- [x] `docs/SPEC_GUIDE.md`：无需更新。本 unit 未改变文档体系。

## Recommended Next Step

Do not accept `refactor-454` as fully passed. Close the remaining blocker by running Feishu/Lark true-platform private/group/non-mention/offline-main-path journeys with a credentialed channel. Separately either provide a live-stack relay redelivery harness for reviewer acceptance or explicitly route that Scenario to verifier-owned regression evidence instead of product-review pass/fail.

# Round 3 - Main-Session Acceptance Routing Addendum

## Summary

This addendum only resolves the ownership of the relay-redelivery Scenario from Round 2. It does not change the Feishu/Lark true-platform blocker.

| Item | Round 3 result | Evidence |
|---|---|---|
| Same logical `relay.message` frame delivered twice | reclassified as verifier-owned regression, not product-review journey | Public IM user APIs can create/send messages, but they cannot force the already-connected IM server to resend one identical server-to-client Gateway WS frame. Regression coverage now explicitly drives the Gateway WS client layer with the same `relay.message` frame twice and asserts one inbound callback: `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py::test_im_connection_dedupes_replayed_relay_message_frame`. Existing adapter/store regressions remain: `test_web_relay_adapter_uses_dedup_store_on_accept`, `test_web_relay_adapter_without_store_uses_in_memory_dedup`, and `test_gateway_relay_dedup.py`. |

## Command

```bash
/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/personal_assistant/test_gateway_im_connection_behavior.py::test_im_connection_dedupes_replayed_relay_message_frame tests/unit/personal_assistant/test_gateway_web_relay_adapter.py::test_web_relay_adapter_uses_dedup_store_on_accept tests/unit/personal_assistant/test_gateway_web_relay_adapter.py::test_web_relay_adapter_without_store_uses_in_memory_dedup tests/unit/personal_assistant/test_gateway_relay_dedup.py
# 8 passed
```

## Updated Acceptance Status

| Requirement group | Status | Reason |
|---|---|---|
| Web IM relay duplicate/redelivery behavior | pass for acceptance routing | The behavior is covered by verifier/regression tests at IM WS client + adapter/store layers. It is not a black-box user journey until a future dedicated resend/debug harness exists. |
| Feishu/Lark true-platform journeys | fail/blocking | Still no credentialed Feishu/Lark channel in `~/.nano-assistant/config.yaml` or worktree `.gateway-config.yaml`; private chat, group @Bot, non-mention shadow sync, and IM-offline Feishu main path remain unverified without fake inbound. |

## Recommended Next Step

Do not accept `refactor-454` as fully passed until Feishu/Lark true-platform journeys are run with a credentialed channel, or the release decision explicitly accepts that external-platform caveat.

---

# Round 4 - 2026-07-09

## Verdict

- Verdict: fail
- Highest Required Action: fix-implementation
- Review mode: targeted true-platform Feishu revalidation
- Review worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-refactor-454`
- Branch reviewed: `unit/refactor-454`
- Head reviewed: `f8e88619`
- Needs re-review: true

Round 4 removed the previous credential blocker: `~/.nano-assistant/config.yaml` now contains `feishu:default-agent`, `./scripts/e2e-up.sh` copied it into the worktree `.gateway-config.yaml`, Gateway auto-filled `botOpenId`, and the IM node came online with `last_error=null`.

Feishu true-platform main paths were exercised with real Lark/Feishu user messages, not fake inbound events. Private chat, group @Bot, group non-mention no-trigger, and IM-offline Feishu main reply all worked. The remaining failure is in the internal IM shadow group projection: after a later non-mention group message, the previous Bot reply was also mirrored into the shadow group as an extra `sender.type=user` message with display name `150ff7f2421d975d`. That is user-visible shadow drift, so the Feishu/shadow requirement cannot pass.

## User Journeys Exercised

1. Service takeover and Feishu channel bootstrap
   - Ran `./scripts/e2e-down.sh`, then `./scripts/e2e-up.sh` in the unit worktree.
   - Worktree IM started at `http://127.0.0.1:51964`; node `wt-unit-refactor-454-78625` was `online`, `relay_enabled=true`, `last_error=null`.
   - Redacted `.gateway-config.yaml` summary showed `feishu:default-agent` with `appId`, `appSecret`, and auto-filled `botOpenId`.

2. Feishu private chat to internal IM shadow direct
   - Sent a real Feishu/Lark user DM to the Bot: `refactor-454 acceptance DM 20260709081807. Reply exactly FEISHU-DM-OK-20260709081807`.
   - Feishu P2P history showed the user message and Bot reply `FEISHU-DM-OK-20260709081807`.
   - IM public API showed shadow conversation `default-agent · feishu` with the same user message and agent reply, both `delivery_status=completed`.

3. Feishu group @Bot to internal IM shadow group
   - Created private Feishu group `refactor-454-acceptance-20260709081935` with the current user and Bot.
   - Sent a real group message with `@Bot`: `refactor-454 acceptance group 20260709081935. Reply exactly FEISHU-GROUP-OK-20260709081935`.
   - Feishu group history showed the user @ message and Bot reply `FEISHU-GROUP-OK-20260709081935`.
   - IM public API showed shadow group `default-agent · refactor-454-acceptance-20260709081935 · feishu` with the user @ message and agent reply, both `delivery_status=completed`.

4. Feishu group non-mention context-only sync
   - Sent a real unmentioned group message: `refactor-454 acceptance nonmention 20260709082031. This should sync as context only.`
   - After 20 seconds, Feishu group history contained the unmentioned user message and no new Bot reply for that timestamp.
   - IM public API showed the unmentioned message synced into the same shadow group as a `user` message with display name `你`.
   - The same IM shadow group also gained an extra message at `2026-07-09T00:20:33.169301Z`: `sender.type=user`, display name `150ff7f2421d975d`, content `FEISHU-GROUP-OK-20260709081935`. This content was the previous Bot reply and should not appear as a separate group-user message.

5. Feishu main path while IM is offline
   - Stopped the worktree IM process only; Gateway process remained alive.
   - Sent a real Feishu/Lark user DM: `refactor-454 acceptance IM offline 20260709082233. Reply exactly FEISHU-OFFLINE-OK-20260709082233`.
   - Feishu P2P history showed Bot reply `FEISHU-OFFLINE-OK-20260709082233` while IM was unreachable.
   - Cleaned the worktree stack with `./scripts/e2e-down.sh`.

## Issues

### Issue 1: Feishu shadow group mirrors the Bot's own reply as an extra user message

- Severity: major
- Regression Relation: direct
- Recommended Action: fix-implementation
- Action Rationale: `motivation.md` requires Feishu group shadow behavior to keep group member messages and agent replies visible with the same sender semantics as before. In the real Feishu group journey, the Bot reply first appeared correctly as an `agent` message, but after a later unmentioned group message the same Bot reply also appeared in the IM shadow group as a separate `user` message with display name `150ff7f2421d975d`.
- User-facing impact: A user reading the internal IM shadow group sees a duplicate Bot reply attributed to a user-like sender, which breaks shadow conversation trust and group sender display semantics.
- Evidence:
  - Correct agent shadow message: `sender.type=agent`, content `FEISHU-GROUP-OK-20260709081935`, `created_at=2026-07-09T00:19:52.444574Z`.
  - Erroneous extra shadow message: `sender.type=user`, display name `150ff7f2421d975d`, content `FEISHU-GROUP-OK-20260709081935`, `created_at=2026-07-09T00:20:33.169301Z`.
- Re-review requirement: after fix, rerun the Feishu group @Bot and non-mention journeys against the real platform and verify the shadow group contains exactly the group member messages plus the canonical agent reply, with no extra user-attributed echo of Bot replies.

## Acceptance Criteria Coverage - Round 4 Updates

### Requirement: 外部 channel 与 shadow 会话行为不变 - 组内结论: fail

| Scenario | 期望来源 | Round 4 验证方式 | Round 4 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Feishu 私聊同步到内部 IM shadow 会话 | `motivation.md`, `docs/operator-runbook.md` | Real Feishu/Lark user DM to Bot, then IM public API shadow direct readback | Feishu P2P contained user message + Bot reply `FEISHU-DM-OK-20260709081807`; IM shadow direct `default-agent · feishu` contained matching user + agent messages, both completed | pass | Previous credential blocker closed for private chat. |
| Feishu 群聊 @Bot 触发回复 | `motivation.md`, `docs/operator-runbook.md` | Real Feishu/Lark group with Bot, user @Bot message, then IM public API shadow group readback | Feishu group contained @ message + Bot reply `FEISHU-GROUP-OK-20260709081935`; IM shadow group contained canonical user + agent messages, but later also an erroneous user-attributed echo of the Bot reply | fail | Main Feishu reply worked; shadow projection has duplicate/wrong-sender user-visible drift. |
| Feishu 群聊未 @ 消息只同步上下文 | `motivation.md`, `docs/operator-runbook.md` | Real Feishu/Lark unmentioned group message, 20-second no-reply observation, then IM public API shadow group readback | Feishu group had no new Bot reply for `20260709082031`; IM shadow group synced the unmentioned message, but also showed the previous Bot reply as an extra `user` message | fail | No-trigger behavior passed on Feishu main path; shadow group content was polluted by an extra user-attributed Bot echo. |
| IM 离线时 Feishu 主路径不受影响 | `motivation.md`, `docs/operator-runbook.md` | Killed worktree IM only, kept Gateway alive, sent real Feishu/Lark DM and read Feishu P2P history | Feishu P2P contained user message + Bot reply `FEISHU-OFFLINE-OK-20260709082233` while IM was unreachable | pass | Shadow sync during IM outage was not required; main external path remained usable. |

## Verification Commands

```bash
env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-down.sh
env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-up.sh
LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1 LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1 lark-cli im +messages-send --user-id <botOpenId> --text "refactor-454 acceptance DM 20260709081807. Reply exactly FEISHU-DM-OK-20260709081807" --as user --format json
LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1 LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1 lark-cli im +chat-messages-list --user-id <botOpenId> --as user --page-size 20 --format json
LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1 LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1 lark-cli im +chat-create --name "refactor-454-acceptance-20260709081935" --bots <appId> --as user --format json
LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1 LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1 lark-cli im +messages-send --chat-id <groupChatId> --text "<at user_id=\"<botOpenId>\">Bot</at> refactor-454 acceptance group 20260709081935. Reply exactly FEISHU-GROUP-OK-20260709081935" --as user --format json
LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1 LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1 lark-cli im +messages-send --chat-id <groupChatId> --text "refactor-454 acceptance nonmention 20260709082031. This should sync as context only." --as user --format json
LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1 LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1 lark-cli im +chat-messages-list --chat-id <groupChatId> --as user --page-size 20 --format json
python - <<'PY'
# Login to the worktree IM, list `/im/v1/conversations`, then read
# `/im/v1/conversations/{shadow_conversation_id}/messages`.
PY
kill "$(cat .im.pid)"
LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1 LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1 lark-cli im +messages-send --user-id <botOpenId> --text "refactor-454 acceptance IM offline 20260709082233. Reply exactly FEISHU-OFFLINE-OK-20260709082233" --as user --format json
LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1 LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1 lark-cli im +chat-messages-list --user-id <botOpenId> --as user --page-size 30 --format json
env PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-down.sh
```

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。本轮发现的是 Feishu shadow 投影实现回归，不是跨包架构契约新增。
- [x] `docs/specs/gateway/spec.md`（Gateway 长青行为契约层）：无需更新。现有 Feishu/shadow 契约已经要求外部回复和 shadow sender 语义保持正确。
- [x] `docs/specs/im/spec.md`（IM 长青行为契约层）：无需更新。现有 IM shadow 可见语义足以覆盖本轮问题。
- [x] `docs/specs/cli/spec.md`：无需更新。本轮未触及 CLI 用户契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。现有 worktree e2e/runbook guidance 足够启动隔离栈；Feishu 凭据已在本机持久配置中可用。
- [x] `docs/SPEC_GUIDE.md`：无需更新。本 unit 未改变文档体系。

## Recommended Next Step

Do not accept `refactor-454` as fully passed. The previous "missing Feishu/Lark credentials" blocker is closed, but Round 4 found a real shadow group correctness issue. Route to `fix-implementation`, then Fast-lane re-review the Feishu group @Bot and non-mention shadow journeys with the same true-platform setup.
