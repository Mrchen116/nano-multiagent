# Verification Report: feat-541

> Validation snapshot: `f6c4c223d → 957debccf`

## Summary

Mode: full
Delta range: N/A
Focus issues: N/A
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 5/5 requirement 有实现；M1 代码退出标准可证明，截图证据未落盘 |
| Correctness | 17/17 scenario 有实现；4 条缺回归测试 |
| Coherence | Followed |

2 warning(s), 2 suggestion(s) found. Fix before PR.

派发重点项结论：失败气泡带模型名、`run_status.error.kind`、`replay_last_user` 不复制用户消息、第一次 admit 用 `candidates[0]`、心跳/cron 显式 `submit_message(model=candidates[0])`、Gateway 不 `except ModelError` / 不 import `agent.core`、失败气泡不算真实正文、PA 不把 fallbacks 塞进内核 —— **代码均已落地**。阻塞项是缺测试与缺原型截图，不是缺实现。

## Completeness

- Tasks: M1 六个实施块均有对应代码与 commits（`24ada38e8` / `44b02de9c` / `6c1d51e1f`）。`tasks.md` 无 checkbox，按 design 退出标准核对。
- Spec 覆盖：5 条 requirement 均有实现（配置页折叠备用、可用性失败同轮换模、轻量说明、按聊天粘性、心跳/cron 同链）。
- Prototype / Reference 覆盖：must-match 已投影到 M1 `[reviewer]` / `[worker]` 退出标准；配置卡交互有 vitest；**unit 目录无 1440/375 截图对照**（`progress.md` 写明未跑隔离真栈 e2e）。聊天 / 飞书三条消息顺序由 PA 单测覆盖出站文本，无浏览器/飞书截图。

Worker 退出标准对照：

| 退出标准 | 状态 |
|---|---|
| 组链 / 粘性接到第一次 admit | 有实现 + `test_model_candidate_chain.py` / `test_chat_model_failover.py` |
| 心跳/cron 显式 `model=candidates[0]` | 有实现；调度层只证明「传了 model」，未证明 sticky/canonical 共享 |
| kind 可换则 replay、拒绝则收口、不看 `reply_text`/⚠️ | 聊天路径有测；心跳/cron 共用 helper **无测** |
| replay 不复制用户消息、说明只发一次、配置保存清粘性、auth 仍换、context_length 不换 | 有测 |
| 前端折叠/添加 vitest | 有测（detail + create） |
| 真实浏览器 1440/375 截图落 unit 目录 | **缺失** |
| 失败文案含模型 id、`error.kind` 经 sdk 可见、列表不进内核、PA 不 import `agent.core` | 有测 |

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 失败气泡含模型名 | `src/agent/core/agent/runtime.py:2563-2564` `_build_provider_error_message` | `tests/unit/agent/test_replay_last_user.py:143` | covered |
| `run_status.error.kind` 经 SDK stream | `src/agent/core/runs/registry.py:37-41`；投影 `src/agent/core/runs/error_kind.py:23` | `test_replay_last_user.py:171`；`test_model_error_kind.py` | covered |
| replay-last-user 不追加 user parts | `src/agent/sdk/kernel.py:1783-1828`；runtime `src/agent/core/agent/runtime.py:603-610` 复用 `last_user` 不 `history.append` | `test_replay_last_user.py:200` | covered |
| 仅 provider-error 不阻止 replay | `src/agent/sdk/kernel.py:2771-2772` 跳过 `is_provider_error` | `test_replay_last_user.py:200`（失败气泡后 replay 成功） | covered |
| 已有真实正文则拒绝 replay | `src/agent/sdk/kernel.py:2774-2775` | `test_replay_last_user.py:234` | covered |
| 第一次 admit 用 `candidates[0]` | 聊天 `session_run_coordinator.py:3055-3073`；心跳/cron `kernel_client.py:236-255` + `ensure_agent_runtime:152` | `test_sticky_is_used_on_the_next_admit`；`test_unattended_model_admit.py:14` | covered |
| 聊天 submit 省略 `model=` | `session_run_coordinator.py:1409-1415` | `test_quota_failure_replays_without_copying_user_parts` 断言 `submit_calls` 仅一次 | covered |
| 心跳/cron 显式 `submit_message(model=...)` | `heartbeat_scheduler.py:518-529`；`cron_runner.py:149-163`；shim 仍 `resolve_run_model(explicit=model)` `kernel_client.py:222-226` | `test_scheduler_passes_agent_model_to_submit`；`test_unattended_model_admit.py` | 实现 covered；canonical 粘性未测 |
| Gateway 只看 `error.kind` | `model_fallback.py:21,112-115`；聊天 `session_run_coordinator.py:2188-2191` **不读** `reply_text`/⚠️ | `test_quota_failure_*`；`test_context_length_does_not_replay`；`test_auth_failsover_and_context_length_does_not` | covered |
| 失败气泡不算真实正文 | 内核 `_raise_if_replay_blocked` 跳过 provider-error；Gateway 以 `ReplayLastUserRejected` 为准 | `test_replay_last_user.py:234`；`test_rejected_replay_closes_the_turn_*` | covered |
| PA 不 except ModelError / 不 import `agent.core` | `src/personal_assistant` 无 `from agent.core`、无 `except ModelError`（仅 observer 注释） | `tests/contract/test_model_fallback_boundary.py:18` | covered |
| 备用列表不进内核 | `SessionRuntimeConfig` 无该字段；`project_agent_runtime` 只写 `model=` | `test_model_fallback_boundary.py:14` | covered |
| 组链：无 sticky=`[头]+fallbacks`，有 sticky 从该点截断 | `local_store.py:679-712` | `test_model_candidate_chain.py:41-54` | covered |
| 没配备用 = 单元素链头 | `local_store.py:707-712` | `test_empty_fallbacks_are_just_the_chain_head` | covered |
| 欠费/配额等同轮 replay 备用 | `session_run_coordinator.py:2173-2260` `replay_last_user` | `test_quota_failure_replays_without_copying_user_parts` | covered |
| 上下文超长不换 | `FAILOVER_KINDS` 不含 `context_length` | `test_context_length_does_not_replay` | covered |
| auth 仍换 | `FAILOVER_KINDS` 含 `auth` | `test_sticky_is_used_on_the_next_admit`（`kind=auth`） | covered |
| 整链耗尽留下每条失败气泡、不伪装成功 | `next_candidate` 穷尽则 `raise RuntimeError` / unattended `return outcome` | **无**专门多候选连续失败测试 | 实现有，缺测试 |
| 首次切换说明只发一次，先说明后正文 | 文案 `model_fallback.py:22`；聊天 `_deliver_control_reply` + hold/flush `2250-2259` | `test_switch_notice_is_sent_once_before_backup_reply` | covered |
| 外部通道同一出站 | 复用 `_deliver_control_reply`（与 compact 控制确认相同）`2122-2165` | 无飞书专用测；与 compact 同路径 | 实现 covered |
| 粘在 session，不写回 `default_model` | `ModelStickyStore` 内存；IM profile 仍存原值 | `test_sticky_is_used_on_the_next_admit`；配置 roundtrip 仍 `default_model` | covered |
| `/new` 清粘性 | 换新 `kernel_session_id`，旧 key 自然不用 | 无专门测 | 实现 covered（结构性） |
| 保存主模型/备用列表清该 Agent 全部 sticky | `agent_config_sync.py:1470-1472` `clear_agent` | `test_publishing_changed_fallbacks_clears_agent_sticky` | covered |
| 另一聊天互不影响 | sticky 按 `kernel_session_id` | 无专门测 | 实现 covered（结构性） |
| 心跳/cron 同链 failover | `heartbeat_runner.py:283-361`；`cron_execution_service.py:422-500` → `failover_unattended_run` | **无**驱动该 helper 的测试 | 实现有，缺测试 |
| 心跳复用 canonical 直聊共享粘性 | composition 共用一份 `sticky_store` `composition.py:291-299,670,730`；heartbeat 优先 canonical session `heartbeat_scheduler.py:446-449`；`admit_model(session_id=...)` | `test_unattended_model_admit` 只测 shim，**不经** scheduler canonical | 实现有，缺测试 |
| 备用用该模型默认推理档，跳过 `/effort` overlay | `apply_saved_reasoning=False`；`_reconcile_runtime(skip_effort_overlay=...)` `1886-1891,1984-1985` | 无专门测 | 实现 covered |
| 配置页默认折叠、标签行右侧数量 | `model-fallback-field.tsx:40,61-88`；CSS `global.css:1084-1100` | `agent-detail-page.test.tsx:578`；`agent-create.test.tsx:735` | covered |
| 展开添加、不能选主模型/已占用、目录用尽隐藏添加入口 | `model-fallback-field.tsx:10-12,53-57,99-145` | vitest 覆盖展开/添加；占用/用尽为代码约束 | covered |
| 清空后与未配置等价 | 保存 `model_fallbacks: []`；旧列缺省 `[]` | IM schema/roundtrip；前端无「删到空」用例 | 实现 covered |
| IM `model_fallbacks` 读写 + apply 校验 | domain/SQLite/API；Gateway `normalize_model_fallbacks` `local_store.py:715-760` | IM contract + `test_normalize_drops_primary_and_unknown_ids_raise` | covered |
| coding_cli 无备用链 | `src/coding_cli` 无 fallback/replay 产品逻辑 | 抽查无命中 | covered |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1：Gateway 持链与粘性；内核 per-run 单模型，只开三条缝 | 是 | 粘性 `model_fallback.py:33-96`；内核仅文案/kind/replay；`SessionRuntimeConfig` 无 fallbacks |
| 决策 2：先投失败气泡再同轮 replay；已有真实输出则收口 | 是 | observer 默认不 hold 首次失败；`ReplayLastUserRejected` → sticky 下一候选 |
| 决策 3：粘性键=`kernel_session_id`；第一次 admit=`candidates[0]`；心跳/cron 禁止省略 model | 是 | composition 共用 store；heartbeat/cron 显式 `model=_admit_model(...)` |
| 决策 4：说明走 `_deliver_control_reply`，不走运行页脚 | 是 | `session_run_coordinator.py:2250-2257` `ack_tag="model-fallback-ack"` |
| 决策 5：备用用自身默认档，不沿用主模型强度/`/effort` | 是 | `apply_saved_reasoning=False`；`skip_effort_overlay` |
| 决策 6：读 `error.kind`，不 except ModelError、不 import agent.core；不把 `retryable` 当唯一开关 | 是 | `FAILOVER_KINDS` 含不可重试的 `auth`；contract 禁止 `agent.core` |
| 聊天省略 `model=`，心跳/cron 必须显式 | 是 | coordinator submit 无 `model=`；scheduler/cron 有 |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| 默认折叠：主模型原位，标签行右侧「备用 未设置」，不撑高 | M1 reviewer 折叠不占位；worker vitest | `model-fallback-field.tsx:61-88` | vitest；**无 1440/375 截图** | warning |
| 已配仍折叠：「备用 N 个」 | M1 reviewer 未展开能看出已配 | `fallbackCount` zh.json:400；detail test:599 | vitest | covered |
| 展开后添加/删除/不能选主模型或占用项；目录用尽隐藏添加 | M1 reviewer 展开保存 | `model-fallback-field.tsx:99-145` | vitest 覆盖添加 | covered |
| 清空后折叠文案回到「未设置」 | M1 reviewer 清空 | 保存 `[]` 后 `value.length===0` 分支 | 无前端清空用例 | covered（实现） |
| 聊天：失败气泡→「已改用」→正文；无弹窗 | M1 reviewer Web IM | failover hold + notice + flush | PA 单测出站顺序；无截图 | covered（实现） |
| 飞书同样三条 | M1 reviewer 外部通道 | 同一 `_deliver_control_reply` | 无飞书证据 | covered（实现） |

### 架构自洽（§4.3）

- 依赖方向：PA 只 import `agent.sdk`；IM 不调 agent；合同测试锁住。**通过**。
- 未把 fallbacks 塞进 Kernel runtime。**通过**。
- 未另造平行选模：扩展 `resolve_run_model` 之上的 `resolve_model_candidates`，shim 仍走 `resolve_run_model(explicit=...)`。**通过**。
- coding_cli 不被拖进备用链。**通过**。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（提 PR 前必须修）

1. **心跳/cron failover 循环没有回归测试。**  
   `failover_unattended_run`（`src/personal_assistant/gateway/model_fallback.py:152`）是与聊天 `_failover_chat_if_needed` **平行的第二条产品循环**，由 `heartbeat_runner.py:347` 与 `cron_execution_service.py:486` 调用。现有测试只覆盖聊天循环和「submit_message 传入 explicit model」，没有一次失败 `kind` → `reconfigure` + `replay_last_user` → 说明/收口的 unattended 用例。  
   **怎么改：** 在 `tests/unit/personal_assistant/` 给 `failover_unattended_run`（或 heartbeat_runner / CronRunTerminalConsumer）补：quota 成功换备用、`context_length` 不换、`ReplayLastUserRejected` 粘下一候选。不要再只测 admit 函数。

2. **design 要求的「直聊已粘备用后心跳复用同一 session」单测缺失。**  
   实现上 composition 共用 `sticky_store`，heartbeat 优先 canonical session（`heartbeat_scheduler.py:446-449`），`admit_model(..., session_id=)` 会读该 session sticky（`kernel_client.py:247-255`）。但 `test_heartbeat_scheduler.py:46-47` 的 fake `admit_model` **忽略 `session_id`**，只按 `agent_id` 返回；`test_unattended_model_admit.py` 不经过 scheduler canonical 查找。  
   **怎么改：** 用真实 `InProcessKernelClient` + 共享 `ModelStickyStore`：先在 canonical session 上 `set(sticky=backup)`，让 scheduler 复用该 session_id，断言 `submit_message` 的 `model=="backup"` 且不是 `agent.default_model`。

3. **整链耗尽 scenario 无测试。**  
   实现：`next_candidate` 返回 `None` 后聊天 `raise RuntimeError`（`session_run_coordinator.py:2200-2201`），unattended `return outcome`（`model_fallback.py:185-186`）。spec 要求每个失败候选留下带模型名的失败气泡、没有伪装成功。  
   **怎么改：** 两个备用都 `kind=quota` 失败，断言 `replay_calls` 次数、没有「已改用」、最终仍 failed。

4. **Worker 退出标准要求的 1440/375 截图未落入 unit 目录。**  
   `progress.md` 写明未跑隔离真栈。原型 must-match（折叠不占位 / 已配数量）目前只有 vitest，没有可复查对照图。  
   **怎么改：** 按 design Runbook 用 `e2e-up.sh` 打开新建页+编辑页，1440 与 375 各留折叠/已配/展开截图到 `docs/changes/feat-541-agent-model-fallbacks/`，并在 `M1-impl/progress.md` 写路径。

### SUGGESTION（可以修）

1. **`/new` 与「另一聊天互不影响」无专门测试。** 粘性按 `kernel_session_id` 存放，行为是结构性的。若要锁契约，可在 `test_chat_model_failover.py` 加 chat-a sticky 后 chat-b 第一次 reconfigure 仍是链头。

2. **前端没有「删光备用后折叠文案回到未设置」和 PATCH `model_fallbacks` 的 vitest。** 保存路径已写 `im-agent-config-api.ts:673`。补一条清空 + 一条 `updateAgentConfig` body 含数组即可。

## Corrected Delta Reconciliation

N/A（`verification_mode=full`）

# Round 2

> Validation snapshot: `f6c4c223d → be74b878f`

## Summary

Mode: targeted-closure
Delta range: `e2b77493c..be74b878f`
Focus issues: 心跳/cron failover 循环无测；直聊已粘备用后心跳复用同一 session 无测；整链耗尽无测；1440/375 截图未落 unit 目录
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 4/4 focus issues 关闭；M1 截图退出标准可证明 |
| Correctness | 相关 scenario 现有回归测试；断言对得上 WHEN/THEN |
| Coherence | Followed；delta 未触及架构边界 |

All checks passed. Ready for PR.

R1 四条 WARNING 均已关闭。Delta 另修了 apply 指纹漏 `model_fallbacks`（只改编用无法落盘），属既有 apply 机制补字段，不是平行选模。R1 SUGGESTION-2（前端清空 PATCH）一并关闭；R1 SUGGESTION-1（`/new` / 另一聊天无专测）仍开放、不阻塞。

## Completeness

Worker 退出标准对照（只核 focus 相关项）：

| 退出标准 | 本轮状态 |
|---|---|
| 心跳/cron `kind` 可换则 replay、拒绝则收口 | 关闭：`failover_unattended_run` 现有 quota / context_length / rejected / 整链耗尽单测 |
| 心跳复用 canonical 直聊时共享粘性 | 关闭：真实 `InProcessKernelClient` + 共享 `ModelStickyStore` + `HeartbeatScheduler.tick` |
| 整链耗尽留下失败、不伪装成功 | 关闭：聊天 + unattended 两条 |
| 真实浏览器 1440/375 截图落 unit 目录 | 关闭：关键画面见 `acceptance.md` 文末归档证据 |

## Correctness

| Focus / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| W1 心跳/cron failover 循环 | `heartbeat_runner.py:347`、`cron_execution_service.py:486` → `model_fallback.py:152` | `test_unattended_quota_replays_backup_and_notices_once`（replay 无 `parts`、notice 一次、sticky noticed）；`test_unattended_context_length_does_not_replay`；`test_unattended_rejected_replay_sticks_next_candidate` | **closed** |
| W2 直聊已粘备用后心跳复用同一 session | `heartbeat_scheduler.py:446-449,518-528` `_admit_model(..., session_id=)`；`kernel_client.py:247-255` | `test_heartbeat_reuses_canonical_session_sticky_model`：sticky=`backup` 写在 `canonical-sess`，`submit` 捕获 `model=="backup"` 且 `session_id=="canonical-sess"` | **closed** |
| W3 整链耗尽 | 聊天 `session_run_coordinator.py:2200-2201`；unattended `model_fallback.py:185-186` | `test_exhausted_chain_stays_failed_without_switch_notice`：两次 replay、无「已改用」、`RuntimeError`、`submit_calls==1`；`test_unattended_exhausted_chain_stays_failed_without_notice`：两次 reconfigure/replay、无 notice、仍 failed | **closed** |
| W4 1440/375 截图 | `reviewer-r1/r1-desktop-create-collapsed-modelrow.png` | 新建折叠「备用 未设置」；展开/已配折叠见验收文字记录 | **closed** |
| R1 S2 清空备用 PATCH | `agent-detail-page.test.tsx:609-648` | 删光后折叠「Fallbacks unset」，PATCH `model_fallbacks: []` | **closed**（非 focus，delta 顺带） |
| apply 只改 fallbacks 能落盘 | `agent_config_sync.py:1605` `_agent_operation_payload` 补字段 | `test_config_operation_apply_persists_model_fallbacks` | 对齐 spec 保存路径；非平行机制 |

本轮跑过：`pytest tests/unit/personal_assistant/test_unattended_model_admit.py tests/unit/personal_assistant/test_chat_model_failover.py tests/unit/personal_assistant/test_gateway_config_operations.py` → 21 passed。

## Coherence

| 检查 | 结果 |
|---|---|
| 决策 3：心跳显式 `model=candidates[0]`，canonical 共享粘性 | 遵守；本轮测试经真实 shim + scheduler，不再只测 fake admit |
| 决策 6：只看 `error.kind` | unattended 测试按 kind 分支，不读 `reply_text` |
| §4.3 架构 | payload 补 `model_fallbacks` 仍走既有 fingerprint/apply；PA 未 import `agent.core`；未把 fallbacks 塞进内核 |

### Prototype / Reference Contract（focus 截图项）

| Reference contract | Durable evidence | Status |
|---|---|---|
| 默认折叠：标签行右侧「备用 未设置」，不撑高 | `reviewer-r1/r1-desktop-create-collapsed-modelrow.png` | covered |
| 已配仍折叠：「备用 N 个」 | 验收文字记录；关键画面见 `acceptance.md` 文末归档证据 | covered |
| 展开后添加/删除入口 | 验收文字记录；关键画面见 `acceptance.md` 文末归档证据 | covered |

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（提 PR 前必须修）

无。

### SUGGESTION（可以修）

1. **（继承 R1）`/new` 与「另一聊天互不影响」无专门测试。** 粘性按 `kernel_session_id` 存放，行为是结构性的。若要锁契约，可在 `test_chat_model_failover.py` 加 chat-a sticky 后 chat-b 第一次 reconfigure 仍是链头。

## Corrected Delta Reconciliation

> Mode: corrected-delta · snapshot `f6c4c223d → aa11eb4e0` · delta 在 `docs/changes/feat-541-agent-model-fallbacks/specs/`，canonical 已归并到 `docs/specs/`。REMOVED 均为空。不重验收 full/targeted 结论。

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `specs/kernel/runs.md` ADDED：消费者可在模型失败后复用上一条用户消息换模型再跑 | SDK `Kernel.replay_last_user` `src/agent/sdk/kernel.py:1783-1828`；runtime 复用 `last_user` 不 `history.append` `src/agent/core/agent/runtime.py:597-610`；不读 fallbacks；产品层只看 `error.kind` | `tests/unit/agent/test_replay_last_user.py:202`；合同导出 `tests/contract/test_agent_sdk_surface_contract.py` | aligned |
| Scenario: replay 不复制用户消息 | 同上；新 run `parts=()` + `replay_last_user=True` | `test_replay_last_user_does_not_append_another_user` 断言用户消息仍一条、第二次请求走 backup-model | aligned |
| Scenario: 仅 provider-error 气泡不阻止 replay | `_raise_if_replay_blocked` 跳过 `is_provider_error` `src/agent/sdk/kernel.py:2771-2772` | `test_replay_last_user.py:202`（失败气泡后 replay 成功） | aligned |
| Scenario: 已有真实输出则不可 replay 原位重放 | 非 provider-error assistant / tool 事件抛 `ReplayLastUserRejected` `kernel.py:2767-2777` | `test_replay_last_user_rejects_non_provider_error_output` `test_replay_last_user.py:236` | aligned |
| `specs/kernel/model-runtime.md` ADDED：失败对消费者可见时必须带上该 run 的模型 id | `_build_provider_error_message` `src/agent/core/agent/runtime.py:2542-2558` 文案 `⚠️ 模型调用失败（{model_id}）:`；`is_provider_error` 仍滤出下一轮上下文 | `test_provider_error_bubble_includes_model_id` `test_replay_last_user.py:145` | aligned |
| Scenario: 失败文案含模型 id | 同上 | 同上，断言 `primary-model` 出现在 assistant 文案 | aligned |
| `specs/kernel/model-runtime.md` ADDED：run 失败终态向消费者暴露可判定的错误种类 | `project_model_error_kind` `src/agent/core/runs/error_kind.py:13-54`；registry `_project_run_failure` `src/agent/core/runs/registry.py:31-51` 把 `kind` 写入 `run_status.error`；PA 经 SDK stream 读取，合同禁止 `agent.core` | `test_failed_run_status_exposes_kind_on_stream` `test_replay_last_user.py:173`；`tests/unit/agent/runs/test_model_error_kind.py`；`tests/contract/test_model_fallback_boundary.py:18` | aligned |
| Scenario: 可用性失败带 kind | quota/overload/timeout/rate_limit/auth 投影；`TimeoutError`/`run_timeout`/`408`/`timed out` → `timeout` `registry.py:42-46,845` | `test_model_error_kind.py` 各 kind 用例；stream 断言 `error.kind=="quota"` | aligned |
| Scenario: 上下文过长带独立 kind | `context_length` 独立；compaction `ModelError` 终态投影 `other`，不进 `FAILOVER_KINDS` | `test_model_error_kind.py` context_length；compaction 集成断言 kind=`other` | aligned |
| `specs/im/agents-nodes.md` ADDED：配置页可设置有序备用模型，且默认不占地方 | `model-fallback-field.tsx:40-88` 默认折叠、数量在标签行右侧；主模型 select 仍由页面 children 原位传入；保存 `model_fallbacks` | detail `agent-detail-page.test.tsx:578`；create `agent-create.test.tsx:735` | aligned |
| Scenario: 默认折叠，主模型选择仍是重点 | `aria-expanded=false`；未展开无「+ 添加备用」 | 同上两条 vitest | aligned |
| Scenario: 展开后按序添加备用并保存 | 展开添加/序号 select；IM 有序 JSON 落盘 `src/IM/infra/repositories/agents.py:283-309,813-815` | vitest 展开添加；`test_model_fallbacks_roundtrip_and_missing_column_defaults_empty`；config contract PATCH 保序 | aligned |
| Scenario: 清空备用后与从未配置等价 | 保存 `[]`；缺省列 `DEFAULT '[]'` `src/IM/infra/db.py:64,757-759` | `agent-detail-page.test.tsx:609` PATCH `model_fallbacks: []`；schema 旧行缺省 `[]` | aligned |
| Scenario: 自动切换不改写编辑页主模型 | 粘性只在 Gateway 内存 `ModelStickyStore`；IM `default_model` / `model_fallbacks` 不因 failover 写入 | 配置 roundtrip 仍是保存值；聊天 sticky 测不断言改 profile | aligned |
| `specs/im/agents-nodes.md` MODIFIED：配置中心可读可改，纳入有序 `model_fallbacks` | API/schema/domain 增加字段；apply 指纹含 `model_fallbacks` `agent_config_sync.py:1601-1610`；Gateway `normalize_model_fallbacks` `local_store.py:715-760` | `test_agent_config_contract.py:52-64,165`；`test_config_operation_apply_persists_model_fallbacks` | aligned |
| Scenario: 读配置暴露稳定字段集（含 `model_fallbacks`） | GET 投影 `src/IM/api/routes/agents.py:271` | `test_agent_config_contract.py:52-64` 断言字段与缺省 `[]` | aligned |
| Scenario: 既有聊天下一轮采用更新后的模型、备用列表和推理强度 | 下轮 `_project_runtime` 读最新 catalog + 组链 `session_run_coordinator.py:1876-1904,3100-3118` | apply 落盘测 + 组链测；既有「下轮才换配置」路径未改 | aligned |
| Scenario: 保存的备用模型必须属于 Gateway apply 时的有效模型目录 | `normalize_model_fallbacks` 目录外 `ValueError`、去重、去掉有效主模型 | `test_normalize_drops_primary_and_unknown_ids_raise` `test_model_candidate_chain.py:64` | aligned |
| MODIFIED 其余既有 Scenario（PATCH 乐观锁、推理档校验、ACK 恢复、live 合并、heartbeat cadence） | 正文只插入 `model_fallbacks`，未改这些路径 | 既有 IM/Gateway 配置测仍覆盖 | aligned |
| `specs/gateway/agent-capabilities.md` ADDED：主模型可用性失败时按有序备用链换模型，本轮继续回复 | 组链 `resolve_model_candidates` `local_store.py:679-712`；聊天 `_failover_chat_if_needed` `session_run_coordinator.py:2206-2306`；`FAILOVER_KINDS` `model_fallback.py:21,110-113`；粘性不写回 `default_model`；备用 `apply_saved_reasoning=False` + `skip_effort_overlay` `session_run_coordinator.py:1897-1904,1924,2348-2354,3120-3124`；说明 `SWITCH_NOTICE_TEMPLATE` 经 `_deliver_control_reply` `ack_tag="model-fallback-ack"` | `tests/unit/personal_assistant/test_chat_model_failover.py`；`test_model_candidate_chain.py`；`test_model_fallback_boundary.py:14` | aligned |
| Scenario: 欠费或服务不可用时本轮仍收到回复 | quota/auth 等 `should_failover` → `replay_last_user`，聊天 submit 省略 `model=` `session_run_coordinator.py:1414-1420` | `test_quota_failure_replays_without_copying_user_parts`；`test_sticky_is_used_on_the_next_admit`（`kind=auth`） | aligned |
| Scenario: 上下文太长不换模型 | `FAILOVER_KINDS` 不含 `context_length` | `test_context_length_does_not_replay` | aligned |
| Scenario: 没配备用时失败呈现与现在一样 | 空 fallbacks → 单元素链头 `local_store.py:707-712`；`next_candidate` 穷尽则收口，不塞平台默认当备用 | `test_empty_fallbacks_are_just_the_chain_head` | aligned |
| Scenario: 整条备用链都失败时按现状失败呈现 | 聊天穷尽 `raise RuntimeError` `session_run_coordinator.py:2234-2235`；无「已改用」 | `test_exhausted_chain_stays_failed_without_switch_notice` | aligned |
| Scenario: 已有真实回复后再失败则本轮不换 | `ReplayLastUserRejected` → 本轮收口并 sticky 下一候选 `session_run_coordinator.py:2246-2254`（与 design 决策 2/粘性状态机一致） | `test_rejected_replay_closes_the_turn_and_sticks_next_candidate` | aligned |
| Scenario: 首次切换有轻量说明，粘住后不再每条提示 | 先 `_deliver_control_reply` 再 flush 正文；`noticed` 后不再发 | `test_switch_notice_is_sent_once_before_backup_reply` | aligned |
| Scenario: 粘在当前聊天，不改写保存的主模型 | sticky 键=`kernel_session_id`；IM profile 仍存原 `default_model` | `test_sticky_is_used_on_the_next_admit` | aligned |
| Scenario: `/new` 或改模型配置后重新从主模型试起 | `/new` 换 kernel session，旧 key 自然不用 `model_fallback.py:36-37,82-94`；保存主模型/备用 `clear_agent` `agent_config_sync.py:1472-1477` | 改配置：`test_publishing_changed_fallbacks_clears_agent_sticky`；`/new` 无专测，行为由新 session_id 结构性保证 | aligned |
| Scenario: 另一个聊天互不影响 | sticky 按 `kernel_session_id` 隔离 | 无跨 chat 专测；`test_sticky_store_clears_all_sessions_for_an_agent` 证明按 session 存放。与 R1 SUGGESTION 相同，不构成 delta/实现冲突 | aligned |
| `specs/gateway/agent-capabilities.md` MODIFIED：每次新回复开始时先组链再 admit | `_resolve_agent_model` 用 `candidates[0]`（有 sticky 即备用）`session_run_coordinator.py:3100-3118`；无备用无 sticky 时链头即本轮模型；保存链变更清粘性 | `test_sticky_is_used_on_the_next_admit`；`test_candidates_with_sticky_skip_earlier_models` | aligned |
| MODIFIED 既有 Scenario（选模型+推理档、改配置保留历史、进行中整轮不换、空 default_model 覆盖强度、heartbeat/cron 完整配置） | 只把 admit 从裸 `default_model` 改成组链后的 `candidates[0]`；链头仍走原 reasoning/`/effort` | 既有能力测 + 本 unit 组链/粘性测 | aligned |
| `specs/gateway/heartbeat-cron.md` ADDED：心跳与 cron 走同一条备用链 | `failover_unattended_run` `model_fallback.py:150-241`；heartbeat `heartbeat_runner.py:287-364`；cron `cron_execution_service.py:422-500`；admit/submit 显式 `model=candidates[0]` `heartbeat_scheduler.py:518-528`、`cron_runner.py:149-161`、`kernel_client.py:217-258` | `test_unattended_model_admit.py` | aligned |
| Scenario: 心跳在主模型不可用时仍能完成 tick | 同上 helper：quota replay、notice 一次、失败气泡带模型名走内核文案 | `test_unattended_quota_replays_backup_and_notices_once` | aligned |
| Scenario: 心跳复用已粘备用的直聊时仍用备用 | canonical session + 共享 `ModelStickyStore`；submit 捕获 `model==backup` | `test_heartbeat_reuses_canonical_session_sticky_model` | aligned |
| Scenario: 定时任务在主模型不可用时仍能跑完 | cron 与 heartbeat 共用 `failover_unattended_run` | 同上 unattended 四条（quota / context_length / rejected / exhausted） | aligned |
| `specs/gateway/external-channels.md` MODIFIED：用户可见事件含备用切换说明，与压缩控制确认同一投递形态 | 聊天 `_deliver_control_reply` `session_run_coordinator.py:2155-2198,2295-2302`（与 `/compact` 同函数）；按 `reply_context` 触发源路由，不是运行页脚 | `test_switch_notice_is_sent_once_before_backup_reply` 走该出站；飞书/IM 分流复用既有控制确认路径 | aligned |
| Scenario: 飞书触发的模型备用切换说明回到原 chat | `_bg_reply_sender` / outbound 与 compact 相同；飞书触发的 `reply_context` 回原 chat 并同步 shadow | 无飞书专用新测；与既有「控制确认外发」同一函数，delta 未另造通道 | aligned |
| Scenario: 内部 IM 触发的模型备用切换说明不回写飞书 | 内部 IM `reply_context` 只留 Web IM | 同上，触发源规则未改 | aligned |
| MODIFIED 既有 Scenario（`/stop` `/new` `/compact`、预处理失败、后台文本、self-evolution、其它内部事件不外发） | 只把「轻量说明」加入用户可见事件清单，未改这些命令语义 | 既有 external-channels / stop 测 | aligned |

### Uncovered Observable Behavior

None。unit 代码 diff（`f6c4c223d..aa11eb4e0`）里后续修补——换模后释放 session busy、timeout kind 补齐、`/stop` 时 flush 被 hold 的备用正文、create payload 带空 `model_fallbacks`、compaction 溢出 kind=`other`——分别落在「心跳同链可跑」「kind 区分超时」「先说明后正文的 hold 不得留下空泡」「缺省 `[]` 与从未配置等价」「compaction 不换模型」这些已有 delta 句下，没有多写新的对外产品行为。

与 unit `spec.md` / `design.md` 对照：Gateway 持链、内核三条缝、第一次 admit=`candidates[0]`、心跳/cron 禁止省略 `model=`、说明走控制确认、备用跳过主模型强度与 `/effort`、只读 `error.kind`，均与实现一致。delta 没有把失败气泡当成真实正文，也没有要求内核持有 fallbacks。

Outcome: aligned
