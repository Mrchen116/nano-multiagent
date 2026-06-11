# Verification Report: bugfix-404

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 15/15 tasks DONE; all incident.md requirements covered |
| Correctness | All scenarios covered; implementation matches spec |
| Coherence | Followed（5 个关键决策全部遵守） |

No critical issues. 1 warning to consider. Ready for PR (with noted improvements).

---

## Completeness

### Task 完成情况

- M1-notify: 3/3 roadpoints DONE（R1=BackgroundTaskRecord 补字段，R2=工具注册传值，R3=_deliver_notification 改造）
- M2-workspace: 3/3 roadpoints DONE（R1=node.register 种子，R2=sync_agent 不采用 mirror，R3=update_profile 封口）
- M3-relay-bg-notify: 3/3 roadpoints DONE（R1+R2=实现+单测，R3=live e2e+spec 文档）；M3 过程中发现两个根因补丁（R4 大小写 bug，R5 outbound_router no-op 问题）均已修复。

Tasks: 15/15（含 M3 R4/R5 补丁 roadpoints）

### Spec 覆盖

incident.md 的两个缺陷修复方向全部落地：

**缺陷一（#8 后台通知丢失）**：
- workspace_root 随任务全程携带 ✓
- 投递失败可观察（log_error）✓
- subagent 跳过语义保留 ✓
- bash + subagent 完成通知送达 parent session ✓
- M3 完成后台 run 回复中继回 IM 对话 ✓

**缺陷二（#79 workspace 隔离失效）**：
- node.register 帧携带 agent_workspaces 种子 ✓
- IM 首见种子落库（幂等） ✓
- sync_agent 不采用 mirror workspace_root ✓
- update_profile 封口（workspace_root 不可变）✓
- worktree e2e live 验证通过（workspace_is_default=False） ✓

---

## Correctness

### M1 — kernel 后台通知（incident.md 缺陷一）

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| BackgroundTaskRecord 补 workspace_root 字段 | `src/agent/core/background_tasks/models.py:59` | `test_register_bash_carries_workspace_root`，`test_register_subagent_carries_workspace_root` | covered |
| bash 工具注册时传 workspace_root | `src/agent/platform/tools/builtins/bash.py:271,353` | `test_bash_tool_run_background_passes_workspace_root_to_registry` | covered |
| agent 工具注册时传 workspace_root | `src/agent/platform/tools/builtins/agent.py:179,256,413` | tests/unit/agent/background_tasks/test_background_tasks.py | covered |
| _deliver_notification 删裸 except pass，log_error | `src/agent/platform/background_tasks/wiring.py:181-188` | `test_deliver_notification_logs_error_on_submit_failure` | covered |
| 子 session（kind=subagent）跳过 submit | `src/agent/platform/background_tasks/wiring.py:164-171` | `test_deliver_notification_skips_subagent_parent_session` | covered |
| submit 透传 workspace_root | `src/agent/platform/background_tasks/wiring.py:173-179` | `test_deliver_notification_submits_for_top_level_session` | covered |
| 前台 budget 内完成不发通知（#19 不回归） | `src/agent/platform/tools/builtins/bash.py:329-337`（notified=is_foreground） | `test_background_tasks.py` foreground 路径 | covered |

### M2 — workspace 隔离（incident.md 缺陷二）

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| node.register 帧携带 agent_workspaces | `src/personal_assistant/reporter/upstream_reporter.py:305-309` | `test_send_register_includes_agent_workspaces` | covered |
| _handle_register 首见用上报值，已存在保持 | `src/IM/ws/gateway_handler.py:872` | `test_handle_register_with_agent_workspaces_seeds_first_seen_profile`，已存在不覆盖，无字段退回旧行为 3 个测试 | covered |
| sync_agent 不采用 mirror workspace_root | `src/personal_assistant/main.py:335-338` | `test_sync_agent_ignores_mirror_workspace_root_and_uses_local_config` | covered |
| ConfigService.update_profile 无 workspace_root 参数 | `src/IM/application/config_service.py:165-213` | `test_update_profile_preserves_non_default_workspace_root` | covered |
| repo 层 UPDATE 不写 workspace_root 列 | `src/IM/infra/repositories.py:1875-1907`（SQL 语句不含 workspace_root） | 同上 | covered |

### M3 — relay 中继（post-M1 补完）

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| BackgroundSessionEventSubscriber 新增 bg_run_output_callback | `src/personal_assistant/gateway/background_session_events.py:75,88` | `test_bg_subscriber_routes_background_task_assistant_message_to_callback` | covered |
| _BACKGROUND_TASK_ORIGIN = "background_task"（小写） | `src/personal_assistant/gateway/background_session_events.py:33` | `test_bg_subscriber_routes_background_task_assistant_message_to_callback`（origin="background_task"） | covered |
| 非 BACKGROUND_TASK origin 不走 bg_run_output_callback | `src/personal_assistant/gateway/background_session_events.py:140-155` | `test_bg_subscriber_ignores_non_background_task_assistant_message` | covered |
| InboundPipeline._bg_reply_sender + send_agent_message | `src/personal_assistant/gateway/inbound_pipeline.py:769-787` | `test_ensure_background_subscriber_wires_bg_run_output_callback` | covered |
| self_evolution_review 既有语义不受影响 | `src/personal_assistant/gateway/background_session_events.py:156-167` | `test_background_subscriber_calls_callback_on_self_evolution_review`（11 个 subscriber 单元测试全绿） | covered |
| live e2e：BG404M3DONE 到达 IM 第二条消息 | M3 progress.md R5 段 | live e2e 2026-06-11 21:52 实测（progress.md R5） | covered（证据记 progress.md） |

---

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1: workspace_root 随任务记录全程携带（注册时捕获，投递时透传） | 是 | `models.py:59`（字段），`bash.py:271`（注册），`wiring.py:179`（透传） |
| 决策 2: 投递失败必须可观察，subagent 跳过改为显式判别 | 是 | `wiring.py:163-171`（显式判 kind），`wiring.py:181-188`（log_error 非静默） |
| 决策 3: node.register 帧加带 agent_workspaces，IM 首见种子落库（幂等） | 是 | `upstream_reporter.py:305-309`（帧），`gateway_handler.py:872`（首见种子） |
| 决策 4: sync_agent 回拉不再采用 IM mirror 的 workspace_root | 是 | `main.py:322-338`（注释 + 代码，本地 config 唯一路径） |
| 决策 5: update_profile 删除 workspace_root 参数，service 层封口 | 是 | `config_service.py:165`（签名无参数），`repositories.py:1830`（SQL 不写该列） |

### 架构自洽性（§4.3）

- 依赖方向：M1 修改全在 `agent.core/platform` 内；M2 修改在 `personal_assistant`（只 import `agent.sdk`）和 `IM`；M3 修改在 `personal_assistant`。未跨越 AGENTS.md 的依赖方向硬规则。
- 跨机边界：design 决策 3 明确"种子值必须经 WS 帧传递，IM 绝不直读 gateway workspace 文件"，实现用 `node.register` 帧传递，遵守 Decision G。
- 复用 vs 平行：M3 扩展了既有 `BackgroundSessionEventSubscriber`，新增 `bg_run_output_callback` 分支，而非另造平行订阅器；wiring 模式与既有 `_session_event_callback` / `_kernel_event_observer` 一致。

---

## Issues

### WARNING

**M3 tasks.md 退出标准中对 `test_bg_subscriber_relay_reaches_outbound_channel` 的描述与 R5 修复后语义不一致**

`M3-relay-bg-notify/tasks.md` R1 中列出该测试为"端到端 relay 测试（BG404DONE 到达 channel.sent）"。但 R5 progress.md 确认了真实 IM 发送路径是 `_bg_reply_sender → send_agent_message`，而非 `outbound_router → channel.sent`（后者是 no-op）。该测试实际测的是 `BackgroundSessionEventSubscriber` 调用 `bg_run_output_callback` 的正确性，而测试内部模拟的 `outbound_router.send_text → channel.sent` 路径并不代表生产路径。

测试本身有回归价值（验证 subscriber 调用 callback），但测试名称、docstring 和 tasks.md 中的描述会误导后续维护者认为 `outbound_router → channel.sent` 是实际的 IM 发送路径。

建议：
- `tests/unit/personal_assistant/test_background_session_events.py:438-507`：更新 docstring，说明测试验证的是 subscriber → callback 调用链，而非完整 IM 发送路径；IM 实际发送路径由 `test_ensure_background_subscriber_wires_bg_run_output_callback` + `_bg_reply_sender` 覆盖。
- `docs/changes/bugfix-404-bg-notify-workspace-isolation/M3-relay-bg-notify/tasks.md` R1 项说明可在 progress.md 补一句注记。

（不影响功能正确性，提 PR 后修也可以）

---

All checks passed. Ready for PR.
