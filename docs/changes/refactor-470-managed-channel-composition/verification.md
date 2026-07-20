# Verification Report: refactor-470

## Summary

Mode: full

Delta range: N/A

Focus issues: N/A

requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 11/16 tasks marked complete；所有行为 requirement 均有实现证据 |
| Correctness | 9/9 scenarios covered |
| Coherence | 有偏离 |

## Completeness

- Tasks: **11/16 complete**。M2 4/4、M3 3/3、M4 4/4 已勾选；M1 的五条退出标准仍是未完成状态，见下方 CRITICAL。
- Spec 覆盖：四类 requirement 均有实现落点：managed channel 在线控制由 `gateway/managed_channel_control.py:159-300` 与 `ws/im_connection.py:723-931` 承担；离线 cached startup 及 register replay 在 `gateway/runtime.py:285-290`、`gateway/managed_channel_control.py:281-300`；生命周期在 `gateway/process_lifecycle.py:97-299`、`gateway/runtime.py:226-459`；heartbeat/cron polling 在 `scheduler/heartbeat_runner.py:80-193` 与 `gateway/composition.py:753-822`。
- Prototype / Reference 覆盖：N/A。`design.md:51` 明确本 unit 没有前端变更或 prototype。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| Managed channel 在线保存后无需重启即可使用 | `gateway/managed_channel_control.py:197-235`; `ws/im_connection.py:848-909` | `tests/integration/test_channel_reconcile.py`; `tests/unit/personal_assistant/test_channel_manager.py`; M4 R3 Feishu online evidence (`M4-composition-root-closure/progress.md:106-109`) | covered |
| 无效配置不伪装成功且不影响其他 Bot | `gateway/managed_channel_control.py:197-219` 复用 fail-closed apply；`gateway/channel_manager.py` 是 runtime/generation owner | `tests/unit/personal_assistant/test_managed_channel_control.py:125-144`; `test_channel_manager.py` | covered |
| 停用、删除或替换只作用于目标 channel | `gateway/managed_channel_control.py:221-249`; `ws/im_connection.py:723-806` | `tests/integration/test_channel_removal_reconcile.py`; `test_channel_manager.py` | covered |
| IM 离线重启后缓存 channel 仍可用 | `gateway/runtime.py:285-290`; `gateway/managed_channel_control.py:159-167` | M4 R3 real-Feishu cached-offline message round trip (`M4-composition-root-closure/progress.md:108-111`)；channel manager/store tests | covered |
| IM 恢复后收敛到最新配置 | `gateway/connection_ready.py:59-100`; `gateway/managed_channel_control.py:281-300`; `ws/im_connection.py:723-806` | `tests/unit/personal_assistant/test_gateway_reconnect_registration_gate.py`; `test_managed_channel_control.py:74-108`; channel reconcile integration tests | covered |
| Gateway start、stop、restart 结果不变 | `gateway/process_lifecycle.py:97-299`; `gateway/runtime.py:226-459` | `test_gateway_launch.py`; `test_gateway_pid_lifecycle.py`; runtime/shutdown suites | covered |
| 新节点 auto-bind 保持 | `gateway/connection_ready.py:59-100`; `gateway/im_bootstrap.py` | `tests/unit/personal_assistant/test_auto_bind.py`; `test_gateway_reconnect_registration_gate.py` | covered |
| Heartbeat 有内容冒泡、无内容静默 | `scheduler/heartbeat_runner.py:135-262` | `tests/unit/personal_assistant/test_heartbeat_im_delivery.py`; `test_cron_polling_runner.py` | covered |
| Cron 定时与手动运行保持隔离语义 | `gateway/composition.py:687-822`; `scheduler/heartbeat_runner.py:159-183` | `tests/unit/personal_assistant/test_cron_polling_runner.py`; M4 R3 true-stack cron evidence (`M4-composition-root-closure/progress.md:106-107`) | covered |

本轮实际执行：

- `PYTHONPATH=src .venv/bin/pytest -q`（所列 refactor 边界测试）→ **102 passed**。
- `.venv/bin/ruff check src/personal_assistant tests/unit/personal_assistant tests/integration tests/contract` → passed。
- `.venv/bin/ruff format --check src/personal_assistant tests/unit/personal_assistant tests/integration tests/contract` → **290 files already formatted**。
- `PYTHONPATH=src .venv/bin/pytest -q tests/contract/test_personal_assistant_main_contract.py tests/contract/test_gateway_inbound_ownership_contract.py tests/contract/test_test_naming_and_size_contract.py` → **23 passed**。
- `PYTHONPATH=src .venv/bin/pytest -q -m "not e2e"` → **3618 passed, 1 skipped, 20 deselected**。

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1：typed bindings，mailbox 不拥有 durable state / ACK / FIFO；fatal owner mismatch 在 receive stack 同步 close | 是 | `gateway/managed_channel_control.py:89-120, 251-278`; `ws/im_connection.py:460-501, 910-932`; regressions `test_gateway_status_frame_ownership.py:143-208, 211-306` |
| 决策 1：ChannelManager / ManifestStore / IMConnectionManager 仍各自拥有 runtime、durable outbox、wire FIFO | 是 | `gateway/managed_channel_control.py:142-155, 281-300`; `ws/im_connection.py:530-580` |
| 决策 1：skill activation 走正式 public operation，不穿透 private API | 是 | `gateway/agent_config_sync.py:262-272`; `gateway/managed_channel_control.py:147-151` |
| 决策 2：删除 standalone YAML → managed manifest bridge，保留空 bootstrap handshake | 是 | `ws/im_connection.py:863-873`; `tests/integration/test_channel_bootstrap.py:128-174`；旧脚本和 legacy migration test 已删除 |
| 决策 3：main 仅 CLI entry，runtime/lifecycle/bootstrap/heartbeat/kernel adapter 使用具名 owner | 是 | `main.py:12-14, 38-123`; `gateway/runtime.py:141-459`; `gateway/process_lifecycle.py:97-299`; `gateway/im_bootstrap.py`; `scheduler/heartbeat_runner.py:24-270`; `gateway/kernel_client.py:18-209` |
| 决策 3：composition 只构造对象图，不承载 credential / retry / lifecycle policy，剩余 helper 回到最近 owner | 否 | `gateway/composition.py:225-332, 942-1092, 1183-1325` 仍实现 bot credential probe/持久化、token refresh/persist、session-fork、permission-response、attachment-fetch 等策略；这些 helper 也被测试直接导入 |

架构边界方面，生产 `personal_assistant` 仅从 `agent.sdk` 导入内核（`gateway/composition.py:343`，`gateway/kernel_client.py:15,126`），没有新增对 `agent.core` / `agent.platform` 的生产依赖；IM 也未反向依赖 Gateway。managed channel 复用了既有 manager/store/connection owner，没有形成第二套 durable queue 或 wire transport。

## Issues

### CRITICAL（提 PR 前必须修）

- **M1 的所有退出标准仍未完成标记，导致任务完成度为 11/16。** `docs/changes/refactor-470-managed-channel-composition/M1-managed-channel-control/tasks.md:11-15` 的五项均为 `- [ ]`，但同文件 `:29-42` 又将三个 roadpoint 写为 DONE，和 `progress.md` 的验证证据矛盾。按 task gate，以下尚未完成项必须在提 PR 前逐项关闭：在线 apply/reconnect/失败隔离/离线 cached startup/register replay；`ManagedChannelControl` 三入口与 mailbox ownership；public skill activation；empty bootstrap 与 legacy bridge 删除；相关 tests/ruff。应逐项复核已有实现和测试证据，确认满足后将 `tasks.md:11-15` 改为 `- [x]`；若任一项尚未满足，应保留未勾选并创建对应修复 roadpoint，而非将 M1 当作完成。

### WARNING（应该修）

- **composition root 仍承担多个有状态或策略性 helper，偏离决策 3 与 M4 exit criterion。** `gateway/composition.py:225-332` 负责 Feishu credential probe；`:942-1004` 负责 owner identity 持久化；`:1007-1092` 刷新/登录并持久化 IM token；`:1094-1181` 处理 session fork；`:1224-1253` 处理 permission response；`:1255-1277` 处理 attachment fetch。它们不只是无状态参数投影，且其中 token/owner persistence 属于 credential policy。对应测试也直接取用这些 private helper，例如 `tests/unit/personal_assistant/test_gateway_build_runtime.py:165-299`、`tests/unit/personal_assistant/test_session_fork_handler.py:40`、`tests/unit/personal_assistant/test_permission_response_handler.py:15`、`tests/unit/test_feishu_integration.py:18`。应把每项转移至其已存在的最近 owner（IM auth/bootstrap、session binder/relay、permission owner、attachment resolver、static Feishu config owner），由 composition 只实例化和注入；测试改为从该真实 owner 测可观察行为。随后将 `gateway/composition.py` 收为纯对象图组装，满足 `design.md:226-230` 和 `M4.../tasks.md:13-15`。

### SUGGESTION（可以修）

- `gateway/composition.py:373-375` 的注释仍说“manifest migration removes them”，而决策 2 已删除该 migration（`design.md:175-204`）。删除或改写该历史失效表述，避免维护者误以为 legacy bridge 仍会运行。

1 critical issue(s) found. Fix before PR.

# Round 2

## Summary

Mode: targeted-closure

Delta range: `a8494e1ba9dbbce1a0f6dd0aa9bd220bb5777095..0e6cee1ebeb427984133523aa9121ed7c3c8f812`

Focus issues:

1. CRITICAL: M1 five exit criteria unchecked (`M1-managed-channel-control/tasks.md:11-15`).
2. WARNING: composition root retains credential/token/session-fork/permission/attachment policy.

requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 11/16；focus issue 1 still open |
| Correctness | 未重跑：delta 未触及生产实现或测试 |
| Coherence | focus issue 2 still open |

## Targeted Closure

- **CRITICAL — still open.** 增量只新增 `docs/changes/refactor-470-managed-channel-composition/acceptance-round-1.md`，未修改 `M1-managed-channel-control/tasks.md`；该文件 `:11-15` 仍全部为 `- [ ]`。因此 M1 退出标准仍未完成标记，任务完成度仍为 11/16。需逐项在 `tasks.md:11-15` 根据已有实现/测试证据改为 `[x]`，或若仍有真实缺口则留下未勾选并建立 fix roadpoint。
- **WARNING — still open.** delta 未修改 `src/personal_assistant/gateway/composition.py`。Round 1 所列 policy helper 仍在 `composition.py:191-332, 942-1092, 1094-1181, 1224-1277`，包括 Feishu credential probe/config write、IM token refresh/persist、session fork、permission response、attachment fetch。该布局继续违背 `design.md:226-230` 的 composition boundary。需将每个 helper 移至相应既有 owner，并将其测试由 composition private helper import 改到真实 owner。

## Issues

### CRITICAL（提 PR 前必须修）

- `M1-managed-channel-control/tasks.md:11-15` 仍未标记完成；见本轮 Targeted Closure 的 first item。

### WARNING（应该修）

- `gateway/composition.py:191-332, 942-1092, 1094-1181, 1224-1277` 仍承载策略；见本轮 Targeted Closure 的 second item。

### SUGGESTION（可以修）

- `gateway/composition.py:373-375` 仍保留 “manifest migration removes them” 的失效说明，和已删除的 migration 不一致。

1 critical issue(s) found. Fix before PR.

# Round 2 — Post-rebase correction

## Summary

Mode: targeted-closure

Delta range: `a8494e1ba9dbbce1a0f6dd0aa9bd220bb5777095..88ab6f21ce9ee55998a7d205a202b2c0d2138fe1`

Focus issues:

1. CRITICAL: M1 five exit criteria unchecked (`M1-managed-channel-control/tasks.md:11-15`).
2. WARNING: composition root retains credential/token/session-fork/permission/attachment policy.

requires_full_verification: true

| 维度 | 结果 |
|---|---|
| Completeness | 16/16 tasks complete；focus issue 1 closed |
| Correctness | 两项 focus issue 的定向回归通过；完整 non-e2e 回归有 1 项确定性 contract 失败 |
| Coherence | focus issue 2 closed；新 delta 跨越 architecture boundary，需在 contract 修复后重新 full verification |

前一段 Round 2 结论基于 rebase 前的 `0e6cee1eb`；该结论不适用于本段所列 validated HEAD，以下为本轮权威结论。

## Targeted Closure

- **CRITICAL: M1 exit criteria — closed.** `M1-managed-channel-control/tasks.md:11-15` 已全部为 `[x]`，本 unit 所有 milestone task 均已勾选。实现仍由 `gateway/managed_channel_control.py:160-180, 198-301` 的 cached lifecycle、typed bindings 和 durable-store delegation，以及 `ws/im_connection.py:872-897` 的 reconcile/bootstrap dispatch 承担。定向执行 `test_managed_channel_control.py`、`test_gateway_status_frame_ownership.py`、`test_channel_bootstrap.py`、`test_agent_config_sync_ownership.py` 为 **12 passed**；ruff check/format 通过。
- **WARNING: composition policy ownership — closed.** `gateway/composition.py:168-591` 仅装配和注入对象；不再定义 config loading / Feishu credential identity、token rotation、session fork、permission response、attachment fetch 或 Cron registration/tick policy。对应职责已分别由 `config/local_store.py:367-542`、`auth/im_auth_client.py:143-220`、`gateway/session_binder.py:647-726`、`ws/im_connection.py:160-181`、`gateway/image_attachments.py:105-117` 与 `scheduler/cron_gateway_runtime.py:30-152` 负责；`process_lifecycle.py:115-124` 通过公开 `load_gateway_runtime_config()` 进入 startup config owner。`test_personal_assistant_main_contract.py` 与相关 owner regressions 为 **84 passed**，并且 `test_composition_does_not_own_gateway_policy_handlers` 明确阻止这些 helper/persistence 回流。

本轮还执行了完整 `pytest -q -m "not e2e"`：**3618 passed, 1 skipped, 20 deselected, 2 failed**。其中 `test_card_action_rpc_correlates_result_and_has_timeout_fallback` 单独重跑为 **1 passed**；另一个 contract failure 可稳定复现，见下方 CRITICAL。

## Issues

### CRITICAL（提 PR 前必须修）

- **修复后的 composition ownership delta 使全量 non-e2e 套件保持红色。** `tests/contract/test_gateway_inbound_ownership_contract.py:217-232` 要求 `gateway/composition.py` 同时 import `build_im_http_headers` 与 `normalize_im_http_base_url`。但本轮将 attachment HTTP header policy 归还 `gateway/image_attachments.py:105-117` 后，composition 只需要 `normalize_im_http_base_url`（`gateway/composition.py:56, 393, 413`）；单独执行该 contract 稳定失败。应将该 contract 改为按每个 consumer 的实际公开 transport 依赖断言：`composition` 只要求 `normalize_im_http_base_url`，attachment fetcher 自己要求 `build_im_http_headers`，并继续禁止私有 `_im_http_*` helper。否则测试强迫纯 composition 为满足断言保留无用 import，既违背 `design.md:227-230`，又阻断 CI。该 delta 改动 composition/credential/attachment/cron 架构边界，按 targeted-closure 规则需在修复后重新执行 full verification。

### WARNING（应该修）

- 无。

### SUGGESTION（可以修）

- 无。

1 critical issue(s) found. Fix before PR.

# Round 3

## Summary

Mode: targeted-closure

Delta range: `0e6cee1ebeb427984133523aa9121ed7c3c8f812..b52362df0ba1cf3edba6fff2ea2cd4a241d9b2be`

Focus issues:

1. Round 1 CRITICAL: M1 five exit criteria unchecked (`M1-managed-channel-control/tasks.md:11-15`).
2. Round 1 WARNING: composition root retains credential/token/session-fork/permission/attachment policy.
3. Follow-up closure: Feishu provisioning must belong to the startup config owner; Cron initial registration/recovery must run only after the Gateway event loop starts.
4. Follow-up closure: transport-owner contract must match each real public consumer.

requires_full_verification: true

| 维度 | 结果 |
|---|---|
| Completeness | 16/16 tasks complete；M1 five exit criteria closed |
| Correctness | 定向回归 76 passed、全量 non-e2e 3625 passed，但受本 delta 影响的真栈 Cron 用户旅程失败 |
| Coherence | 三项 ownership focus issue closed；Cron delivery correctness still open，另有 1 项 composition 持久化副作用偏离 |

本轮以 `b52362df0` 为唯一验证对象。Round 2 及其 Post-rebase correction 分别基于错误 delta 和未完成中间态，按 orchestrator 指令仅保留为历史记录，不作为本轮或最终 verdict 的判据。

## Targeted Closure

- **Round 1 CRITICAL: M1 exit criteria — closed.** `M1-managed-channel-control/tasks.md:11-15` 全部为 `[x]`。`gateway/managed_channel_control.py:160-180, 198-301` 保留 cached startup、typed bindings、durable manifest/status owner delegation；`ws/im_connection.py:872-897` 直接执行 reconcile 与空 bootstrap handshake。`test_managed_channel_control.py`、`test_gateway_status_frame_ownership.py`、`test_channel_bootstrap.py` 与 `test_agent_config_sync_ownership.py` 纳入定向回归并通过。
- **Round 1 WARNING: named composition policy ownership — closed.** credential rotation、session fork、permission response、attachment fetch、Cron registration/tick、retry/status/reconcile 已移至真实 owner；composition 未定义上述 policy、`.persist()` 或 sensitive config writer。对应领域 owner 是 `config/local_store.py:367-546`、`auth/im_auth_client.py:143-220`、`gateway/session_binder.py:647-726`、`ws/im_connection.py:160-181`、`gateway/image_attachments.py:105-117` 与 `scheduler/cron_gateway_runtime.py:30-156`；`test_personal_assistant_main_contract.py:59-88` 继续防止这些 policy 回流。另见下方 WARNING：composition 仍含一个未在本轮 focus 中列出的持久化副作用。
- **Startup ownership — structure closed; user-facing Cron correctness still open.** 前台和后台 lifecycle 均通过 `process_lifecycle.py:115-124, 190-194` 调用 `load_gateway_runtime_config()`；该 public startup-config owner 在 `config/local_store.py:367-409` 完成 Feishu identity 和 declared-skill provisioning，之后才交由 `compose_gateway()` 装配。Cron 初始注册/recovery 从 composition 移至 `GatewayCronRuntime.start()`（`scheduler/cron_gateway_runtime.py:105-108`），由 event-loop 已启动的 `GatewayRuntime._run_until_shutdown()` 在 channel producer 之前调用（`gateway/runtime.py:230-241, 277-280`）。`test_gateway_build_runtime.py:91-151` 与 `test_gateway_runtime_lifecycle.py:66-97` 断言无 compose-time 持久化/registration 和真实启动次序；但 rebase 后纳入的同一验证对象 acceptance evidence（`acceptance-round-3.md:29-35, 61-66`）显示真 Gateway/IM 的 Cron 主动消息等待超时。因此本项的 ownership structural closure 不足以关闭受直接影响的用户旅程，见下方 CRITICAL。
- **Transport owner contract — closed.** `tests/contract/test_gateway_inbound_ownership_contract.py:217-248` 逐 consumer 断言：config sync/shadow sync 使用 public URL+headers；composition 仅使用 URL normalization；`gateway/image_attachments.py` 是 headers 的真实 attachment consumer。该 contract 通过，未以无用 import 反向污染 composition。

本轮执行：

- `PYTHONPATH=src .venv/bin/pytest -q`（M1、composition/startup、Cron、transport contracts 的定向集合）→ **76 passed**。
- `PYTHONPATH=src .venv/bin/pytest -q tests/contract` → **193 passed**。
- `PYTHONPATH=src .venv/bin/pytest -q -m "not e2e"` → **3625 passed, 1 skipped, 20 deselected**。
- `.venv/bin/ruff check .` → passed；`.venv/bin/ruff format --check .` → **856 files already formatted**。

## Issues

### CRITICAL（提 PR 前必须修）

- **Cron 定时主动消息在受本启动时序 delta 影响的真栈旅程中未送达用户。** `acceptance-round-3.md:29-35, 61-66` 在 `b52362df0` 上记录：`NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 ... test_cron_push_critical_path.py -o timeout=360 --tb=long` 等待用户可见 agent 消息超时。虽然 `GatewayCronRuntime.start()` 已从 composition 移至 runtime startup（`scheduler/cron_gateway_runtime.py:105-108`; `gateway/runtime.py:230-241`），这项直接用户可观察的 requirement 仍未通过。应诊断 live startup 后 `CronExecutionService` 的注册、gateway loop 注入、scheduled tick 到 terminal delivery 的实际链路，修复后运行该 Cron critical-path e2e，并重新 full verification；不得以 unit/contract 绿替代用户消息往返。

### WARNING（应该修）

- **composition 仍执行 builtin-skill 安装，因而不是纯对象图构造。** `gateway/composition.py:193-203` 在每次 `compose_gateway()` 调用时执行 `install_builtin_skills()`；该操作会创建 `~/.nanoassistant/skills` 并在缺失时复制 packaged skill directory（`builtin_skills/bootstrap.py:16-55`）。这与 `design.md:227-230` 所述 composition 不承载持久化副作用相悖，也使测试或预检的 composition 调用改写用户全局目录。应将该安装操作归入启动 config/provisioning owner（在 `config/local_store.py:367-390` 的 startup 路径与 Feishu provisioning 一并运行），再由 composition 只消费已准备的 config/skill root；补充回归，断言 `compose_gateway()` 不创建或复制用户目录。

### SUGGESTION（可以修）

- 无。

1 critical issue(s) found. Fix before PR.
