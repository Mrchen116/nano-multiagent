# Verification Report: bugfix-525

> Validation snapshot: `cd071e649d3fe4fe7a2f392643a49c8f87825898 → 30a701a522f52ef337141806c39fa3848b93358e`

## Summary

Mode: full

Delta range: N/A

Focus issues: N/A

requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 5/5 M1 退出标准完成；3/3 incident Requirements 与全部 6 个 Scenario 均有实现和长期保护 |
| Correctness | 3/3 delta Requirements、6/6 delta Scenarios 与 incident 目标一致 |
| Coherence | Followed |

## Completeness

- Tasks: 5/5 complete。`M1-lifecycle-routing/tasks.md:11-15` 的 policy、真实副作用、单 owner、跨层回归和质量门禁均有对应实现与本轮实际结果。
- Spec 覆盖：fork 在 `src/agent/core/agent/context_fork.py:18-36,200-290` 依 source policy 隔离 raw event；hook 在 `src/agent/platform/hooks/builtins/self_improvement.py:219-256` 显式选择 policy 并保持 structured notice；Gateway 在 `src/personal_assistant/gateway/background_session_events.py:192-258`、`background_subscriptions.py:172-253`、`runtime_delivery/observer.py:524-538`、`composition.py:466-506` 完成唯一 owner 与既有 config-sync 接线。
- Prototype / Reference 覆盖：N/A。该 M1 是 Kernel/Gateway 生命周期修复，`tasks.md:40` 明确无 UI/prototype contract；R4 隔离真栈的可复查 locator、限制和清理记录在 `M1-lifecycle-routing/progress.md:58-75`，不被当作永久回归测试。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| incident「self-evolution 原始过程保持后台私有」：memory review 正常完成；kernel delta「memory review 不产生第二条 assistant 输出」 | `context_fork.py:18-36,244-290` 只让 self-evolution policy 转发 source-marked `skill_created`；`self_improvement.py:219-256` 仍发布最终 structured review notice | `tests/integration/test_self_evolution_output_visibility.py:36-141` 从 public Kernel 真正执行 `memory(add)`，断言前台文本唯一、review tool/raw output 不在 parent stream、`USER.md` 已写入并收到 notice | covered |
| incident「无保存内容或 review 失败」；routing delta「无更新或失败保持私有」 | allowlist 是 event-kind 而非回复文案过滤（`context_fork.py:18-36`）；hook fork 失败仅记录异常并返回（`self_improvement.py:219-231`），不会影响已完成前台 run | `tests/unit/test_background_hook_fork.py:747-794` 以任意 raw assistant/tool event 证明 content-agnostic filter；`tests/unit/test_background_hook_fork.py:98-116` 覆盖 background handler error isolation | covered |
| incident「skill review 创建新 Skill」；kernel delta「skill review 暴露可归属创建事件」 | `context_fork.py:29-35` 保留 payload 并追加 `source=self_evolution`；`background_session_events.py:220-238` 只把标记事件交业务 callback | `tests/integration/test_self_evolution_output_visibility.py:143-247` 用真实 `skill_manage(create)` 断言 Skill 文件、单一 source-marked event、无 raw review output 与最终 notice | covered |
| incident / capabilities delta「fast、slow review 在 terminal 前后均调和」 | coordinator 以 run start anchor 交给 session manager（`session_run_coordinator.py:880-929`）；manager 以 request 的 agent identity 调既有 handler（`background_subscriptions.py:215-253`） | `tests/unit/personal_assistant/test_background_subscription_manager.py:65-109` 参数化 replay/live；`tests/integration/test_self_evolution_gateway_skill_sync.py:52-179` 让真实 review 在 terminal 后完成，穿过真实 `IMAgentConfigSync` 观察 catalog revision 和落盘 Skill | covered |
| incident / capabilities delta「后续 turn、reconnect/replay 不漏激活、不重复」 | manager 每 session 只建一个 subscriber（`background_subscriptions.py:92-122,233-253`）；subscriber 在每个事件推进 cursor 后按 `after_sequence` 重连（`background_session_events.py:180-282`） | `tests/unit/personal_assistant/test_background_subscription_manager.py:112-157` 覆盖 already-active 的第二轮；`tests/unit/personal_assistant/test_background_session_events.py:163-219` 覆盖 disconnect 后 cursor 8→9，无重复 callback | covered |
| Gateway current contract 与 capabilities delta 的 default/explicit（含显式空）skill 规则 | `agent_config_sync.py:1006-1048` 复用 scope/root validation；`agent_config_sync.py:1050-1099` 保持 default discovery、更新 explicit selection；`agent_config_sync.py:1101-1153` 保留 selection mode | `tests/unit/personal_assistant/test_gateway_im_config_sync.py:465-601` 覆盖 global Skill 对 default、显式非空和显式空 allowlist 的收敛及 revision；`:604-703` 覆盖 agent scope 只影响执行 Agent | covered |
| incident / routing delta「普通 background Agent 用户可见结果不变」 | marked-skill 路由与 `BACKGROUND_TASK` assistant relay 是互斥分支，后者未改为 self-evolution filter（`background_session_events.py:197-238`）；manager 保留原 reply/dedupe path（`background_subscriptions.py:186-213`） | `tests/unit/personal_assistant/test_background_session_events.py:590-654` 与 `test_background_subscription_manager.py:161-197` 覆盖 ordinary background relay；`test_tool_end_detail_passthrough.py:171-257` 证明 unmarked foreground skill 仍属 per-run observer | covered |
| production composition 不会遗漏 persistent owner 的 config-sync 依赖 | 同一个 `IMAgentConfigSync.handle_skill_created` bound method 同时注入 per-run observer 和 manager（`composition.py:466-506`） | `tests/unit/personal_assistant/test_gateway_build_runtime.py:238-265` 捕获 production composition 并断言 manager 获得该 bound method；与上述真实 Kernel→manager→`IMAgentConfigSync` integration 共同覆盖故障 seam | covered |

### Verification evidence

- Focused affected matrix: `102 passed, 2 warnings in 9.12s`，命令覆盖 fork/hook、subscriber/manager/observer、production composition、mode-aware config sync 与两份 self-evolution integration tests。
- Full non-E2E: `3193 passed, 26 deselected, 22 warnings in 232.87s`，命令：`PYTHONPATH=src pytest -q -m 'not e2e'`。
- Quality gates: `ruff check .`、`./scripts/docs-check`（224 maintained Markdown sources / 67 required routes）、`git diff --check 48d19d8..HEAD` 均通过。
- Architecture contracts: `tests/contract/test_cli_sdk_only_contract.py`、`test_core_no_platform_imports.py`、`test_platform_no_sdk_imports.py` 与 `test_bg_origin_constant_contract.py` 共 `7 passed`。实现继续让 product 只消费 `agent.sdk`（`background_subscriptions.py:20-22`），没有引入 `core → platform`、产品互相 import 或 IM→agent 依赖。

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| D1：通用 fork 默认 inherit，self-improvement 显式选择 private policy | 是 | `context_fork.py:200-227,263-273` 默认 `inherit` 且拒绝未知值；`self_improvement.py:219-225` 是唯一显式 `self_evolution` caller；`test_background_hook_fork.py:659-812` 分别保护 generic inherit、opt-in filter/source 与拒绝路径 |
| D2：标记 `skill_created` 始终由 persistent manager 单独拥有，per-run fail-closed 跳过 | 是 | `runtime_delivery/observer.py:524-538` 先跳过 marked event；`background_session_events.py:220-238` 与 `background_subscriptions.py:215-231` 唯一接收并转交；fast/slow、already-active 与 replay 测试见上表 |
| D3：复用既有 `AgentConfigSync.handle_skill_created()`，不新增 config mutation 通道 | 是 | `background_subscriptions.py:215-222` 只在线程中调用注入 handler；`composition.py:466-506` 复用同一 bound method；`agent_config_sync.py:1006-1153` 仍是唯一 mode-aware mutation owner |
| D4：cursor、单 owner 与既有 config-sync 收敛承担 replay idempotency | 是 | `background_session_events.py:183-195,254-282` 在 reconnect 使用最后 sequence；`background_subscriptions.py:92-122` ensure-once；`test_background_session_events.py:163-219` 和 `test_background_subscription_manager.py:112-157` 保护其时序 |
| D5：永久回归必须跨真实 failure seam，避免只证明 Kernel stream | 是 | Kernel 可见性/持久副作用和 Gateway lifecycle 分列 `tests/integration/test_self_evolution_output_visibility.py`（247 lines）与 `test_self_evolution_gateway_skill_sync.py`（179 lines），共享 118-line controlled driver；后者实际观察 `IMAgentConfigSync` 后 catalog revision 和 Skill 文件，不只断言 event 存在 |

实现未新增平行 queue、配置同步或跨机读写机制；按 event source 分配 owner，保留 ordinary `BACKGROUND_TASK` 文本 route。测试按 `docs/development/testing.md` 的最低 failure seam 分层：Kernel private visibility、subscriber lifecycle、per-run ownership、composition wiring 与 real config-sync result 各自保护不同风险；新增文件均低于 400 行，未发现长期重复或一次性验收证据伪装为 test。

## Prototype / Reference Contract

N/A.

## Issues

### CRITICAL（提 PR 前必须修）

- None.

### WARNING（提 PR 前必须修）

- None.

### SUGGESTION（可以修）

- None.

All checks passed. Ready for PR.
