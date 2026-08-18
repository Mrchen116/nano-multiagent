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
| 真实浏览器 1440/375 截图落 unit 目录 | 关闭：8 张 PNG 在 `M1-impl/screenshots/`，`progress.md` 写了路径 |

## Correctness

| Focus / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| W1 心跳/cron failover 循环 | `heartbeat_runner.py:347`、`cron_execution_service.py:486` → `model_fallback.py:152` | `test_unattended_quota_replays_backup_and_notices_once`（replay 无 `parts`、notice 一次、sticky noticed）；`test_unattended_context_length_does_not_replay`；`test_unattended_rejected_replay_sticks_next_candidate` | **closed** |
| W2 直聊已粘备用后心跳复用同一 session | `heartbeat_scheduler.py:446-449,518-528` `_admit_model(..., session_id=)`；`kernel_client.py:247-255` | `test_heartbeat_reuses_canonical_session_sticky_model`：sticky=`backup` 写在 `canonical-sess`，`submit` 捕获 `model=="backup"` 且 `session_id=="canonical-sess"` | **closed** |
| W3 整链耗尽 | 聊天 `session_run_coordinator.py:2200-2201`；unattended `model_fallback.py:185-186` | `test_exhausted_chain_stays_failed_without_switch_notice`：两次 replay、无「已改用」、`RuntimeError`、`submit_calls==1`；`test_unattended_exhausted_chain_stays_failed_without_notice`：两次 reconfigure/replay、无 notice、仍 failed | **closed** |
| W4 1440/375 截图 | `M1-impl/screenshots/*.png`；`progress.md:13-22` | desktop 1440×900 / mobile 375×812；新建折叠「备用 未设置」、编辑折叠「备用 1 个」、展开可见序号 select +「+ 添加备用」 | **closed** |
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
| 默认折叠：标签行右侧「备用 未设置」，不撑高 | `desktop-create-collapsed.png`（1440×900）、`mobile-create-collapsed.png`（375×812） | covered |
| 已配仍折叠：「备用 N 个」 | `desktop-edit-collapsed.png` / `mobile-edit-collapsed.png`（「备用 1 个」） | covered |
| 展开后添加/删除入口 | `*-create-expanded.png` / `*-edit-expanded.png` | covered |

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（提 PR 前必须修）

无。

### SUGGESTION（可以修）

1. **（继承 R1）`/new` 与「另一聊天互不影响」无专门测试。** 粘性按 `kernel_session_id` 存放，行为是结构性的。若要锁契约，可在 `test_chat_model_failover.py` 加 chat-a sticky 后 chat-b 第一次 reconfigure 仍是链头。

## Corrected Delta Reconciliation

N/A（`verification_mode=targeted-closure`）
