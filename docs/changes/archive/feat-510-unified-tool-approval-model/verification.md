# Verification Report: feat-510

> Validation snapshot: `eaaed4c3ec91c5359044ca6b47d3834e8388063f → 89197f46323803d413a012f83418d5dad03049ce`

## Summary

Mode: `full`

Delta range: N/A

Focus issues: N/A

requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 1/1 Milestone 实现范围已落地；独立门禁/归档/PR roadpoint 正在执行 |
| Correctness | 4/4 Requirements 实现匹配；2 个 design/spec 指定的永久测试 seam 未真正覆盖 |
| Coherence | Followed；1 个公开 API docstring 规范建议 |

0 critical issue(s), 2 warning(s) found. Fix before PR.

## Completeness

- Milestone: M1 唯一 milestone 的代码、永久测试、运维文档和可复查 evidence 均存在；`tasks.md` 的实现 roadpoints 为 6/6 完成，第 7 项是正在进行的独立门禁、canonical merge、归档、PR 和 CI 收尾，不是缺失的实现。
- Spec 覆盖: 4/4 Requirements 均能映射到生产实现；7/7 Scenarios 的行为路径均存在。W1/W2 是永久回归保护没有真正经过指定 seam，不是当前生产实现缺失。
- Prototype / Reference 覆盖: N/A；`design.md` 没有前端原型或 reference artifact contract。
- 独立复跑 evidence:
  - `pytest -q tests/unit/personal_assistant/config/test_parse_llm.py tests/unit/personal_assistant/test_gateway_build_runtime.py tests/unit/test_auto_mode_gate_hook.py tests/contract/test_sdk_kernel_wiring.py` → `62 passed`.
  - `PYTHONPATH=src pytest -q tests/e2e/critical_paths/test_tool_approval_model_critical_path.py` → `4 passed in 41.29s`.
  - SDK/core/product import-boundary contract → `8 passed`.
  - 变更 Python 文件 `ruff check` / `ruff format --check`、`git diff --check`、`./scripts/docs-check` 全部通过；docs-check 报告 `237 maintained Markdown sources, 66 required routes`.

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| PA 可统一指定自动工具权限分类模型 / 不同 Agent 共用 C | `src/personal_assistant/config/local_store.py:48-64,996-1088`; `src/personal_assistant/gateway/composition.py:198-214`; `src/agent/sdk/kernel.py:229-330,567-586`; `src/agent/platform/hooks/builtins/auto_mode_gate.py:943-953` | `tests/e2e/critical_paths/test_tool_approval_model_critical_path.py:221-261` 真栈断言 A→C→A / B→C→B | covered |
| 所有 PA 运行来源遵守统一选择 | 模型选择存在 Kernel 单一 HookRegistry，分类入口不按 origin 分支：`src/agent/sdk/kernel.py:567-586`; `src/agent/platform/hooks/builtins/auto_mode_gate.py:943-953` | `tests/unit/test_auto_mode_gate_hook.py:209-225` 覆盖 user/heartbeat/cron，但 Agent 派生的真实值是 `background_task`，测试却传了不存在的 `subagent`；见 W2 | covered with test gap |
| 专用模型不改变 Agent 对话与工具后续模型 | 只有两阶段 classifier 显式传 model：`src/agent/platform/hooks/builtins/auto_mode_gate.py:436-542`；正常 run 仍由 `submit(model=...)` 选择 | `tests/contract/test_sdk_kernel_wiring.py:257-313`; E2E `:221-261` | covered |
| 配置省略审批模型 | parser 产生 `None`，registry state 不保存值，HookContext 回落当前 run model：`src/personal_assistant/config/local_store.py:1012-1019`; `src/agent/platform/hooks/tool_approval_model.py:13-35`; `src/agent/core/agent/runtime.py:1480-1513` | `tests/unit/personal_assistant/config/test_parse_llm.py:47-59`; `tests/unit/test_auto_mode_gate_hook.py:251-264`; E2E `:266-283` | covered |
| 配置未注册的审批模型拒绝启动 | PA parser 在 catalog 建成后字段级校验：`src/personal_assistant/config/local_store.py:1071-1088`；SDK 再守一次所有消费者：`src/agent/sdk/kernel.py:291-330` | `tests/unit/personal_assistant/config/test_parse_llm.py:75-87`; `tests/contract/test_sdk_kernel_wiring.py:239-241`; E2E `:319-345` | covered |
| 专用模型运行时不可用，不改用 Agent 模型 | 两阶段例外/超时/不可解析均产生 ask，没有第二模型选择：`src/agent/platform/hooks/builtins/auto_mode_gate.py:470-542,993-1011`; runtime 单次按显式 model 选 client：`src/agent/core/agent/runtime.py:1480-1513` | `tests/unit/test_auto_mode_gate_hook.py:266-284`; E2E `:286-316` 进入 attended `permission.request` 且 classifier 只记录 `approval-fail` | covered |
| 修改配置后重启才切换 C→D | `compose_gateway` 每个进程仅读取一次并在 build 时写入 registry：`src/personal_assistant/gateway/composition.py:198-214`; `src/agent/sdk/kernel.py:567-586` | E2E `tests/e2e/critical_paths/test_tool_approval_model_critical_path.py:240-261` 先改磁盘配置仍观测 C，restart/reconnect 后观测 D | covered |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| D1: PA-owned `llm.tool_approval_model`，省略=None，空/未注册失败，save round-trip | 是 | `src/personal_assistant/config/local_store.py:48-64,900-931,996-1088` |
| D2: SDK 只增 build-scoped 参数，不污染 `LLMConfig` | 是 | `src/agent/sdk/kernel.py:229-330`; `src/personal_assistant/product.py:381-431` |
| D3: current-main 采用单一 registry-state bridge，不放 session metadata，不与 476 bundle 并存 | 是 | `src/agent/platform/hooks/tool_approval_model.py:1-35`; `src/agent/sdk/kernel.py:531-583`; source 中无 `BuiltinHookDependencies`，getter 的唯一生产 caller 为 canonical auto gate |
| D4: 只给 stage 1/2 classifier 传显式模型 | 是 | `src/agent/platform/hooks/builtins/auto_mode_gate.py:436-542,943-953` |
| D5: 失败沿用 fail-closed ask/unattended，不新增模型回退 | 是 | `src/agent/platform/hooks/builtins/auto_mode_gate.py:470-542,993-1011`; `src/agent/core/agent/runtime.py:1480-1513` |
| D6: Gateway restart 生效，无热更新 seam | 是 | `src/personal_assistant/gateway/composition.py:198-214`; `src/agent/sdk/kernel.py:567-586` |
| D7: 用 Anthropic request body model 作确定性验收锚 | 是 | `scripts/fixtures/anthropic_sse_tool_approval_recording.py:135-173`; `tests/e2e/critical_paths/test_tool_approval_model_critical_path.py:155-218` |

架构自洽性：未发现依赖方向、跨进程边界或平行机制问题。PA 只通过 `agent.sdk` 传递选择，`platform → core`、`sdk → core + platform` 方向保持；相关 contract 独立复跑通过。

### Prototype / Reference Contract

N/A.

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

- **W1 — 两 provider catalog 测试没有经过两个 provider client，无法保护 design 指定的跨 provider 分类路由。** `tests/contract/test_sdk_kernel_wiring.py:257-294` 虽声明 `provider-a/model-a` 和 `provider-c/model-c`，但 build 时传入单一 `_llm_client_override=_RoutingClient()`，使 A/C 全部绕过 `AgentEngine._client_for_model()` 的 provider client map；因而该测试即使把 C 错发给 provider-a client 也会继续通过，与 `design.md:259-260` 的明确测试要求不符。修复时在这个 SDK contract 测试中不使用单 client override，改为 monkeypatch `agent.sdk.kernel._platform_create_llm_client` 为每个 provider 返回独立 recording client，然后同时断言 A 的两次正常请求只进 provider-a client，C 的 classifier 请求只进 provider-c client，且整体 model 序列仍为 A→C→A。
- **W2 — “所有 run origin”的永久测试用了不存在的 `subagent` origin，未覆盖 Agent 派生运行的真实 `background_task` seam。** `tests/unit/test_auto_mode_gate_hook.py:209-225` 参数化为 `user/heartbeat/cron/subagent`，但生产枚举只有 `user/background_task/heartbeat/cron` (`src/agent/core/runs/origin.py:6-14`)，Agent 派生 run 也在 `src/agent/platform/background_tasks/runtime_runner.py:140-169` 显式传 `RunOrigin.BACKGROUND_TASK`。修复时把 `subagent` 替换为 `RunOrigin.BACKGROUND_TASK.value` 或字面值 `background_task`，保留 user/heartbeat/cron；这样才真正保护 spec 的 Agent 派生场景和 design M1 的 different-run-origin 退出标准。

### SUGGESTION（可以修）

- **S1 — 补全公开 SDK 失败契约的 Google-style `Raises`。** `src/agent/sdk/kernel.py:248-290` 的 public `build_kernel` docstring 已增加 `tool_approval_model` Args，但没有说明 `src/agent/sdk/kernel.py:291-330` 的空值/未注册 `ValueError`。按 `docs/development/coding-guidelines.md:14-40` 在 `Returns` 后增加 `Raises: ValueError` 并写明 llm 缺失、审批模型为空或不在 catalog 的失败语义。

# Round 2

> Validation snapshot: `eaaed4c3ec91c5359044ca6b47d3834e8388063f → 7f0d4be1e3d2adf992dd80413a4bed587cbf5ff8`

## Verification Report: feat-510

### Summary

Mode: `full`

Delta range: N/A

Focus issues: Round 1 W1 / W2 / S1，以及 code-review 发现的既有 `_classify_action` 直接调用和 dispatch hook harness 回归

requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 1/1 Milestone；4/4 Requirements，7/7 Scenarios |
| Correctness | 7/7 Scenarios 实现与永久测试覆盖匹配 |
| Coherence | Followed |

All checks passed. Ready for PR.

## Completeness

- M1 的 PA config parse/save/compose、SDK build-scoped 选择、单一 registry-state bridge、auto gate 两阶段路由、失败不回退、重启生效、运维文档和 deterministic 真栈 E2E 均已落地。
- `tasks.md` 的 6 项实现 roadpoint 已完成；独立门禁/canonical merge/归档/PR/CI 是 orchestrator 收尾，不是缺失的实现。
- Prototype / Reference: N/A；本 unit 无原型或 reference artifact contract。
- 独立复跑 evidence:
  - PA config/composition、全部 `test_auto_mode_gate*.py`、SDK wiring/behavior 与架构 contract：`134 passed`.
  - 真 IM + Gateway + 进程内 Kernel critical path：`4 passed in 51.37s`.
  - 变更 Python 文件 `ruff check` / `ruff format --check`、unit diff `git diff --check`、`./scripts/docs-check` 全绿。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 不同 Agent 共用专用审批模型 C | `src/personal_assistant/config/local_store.py:48-64,996-1088`; `src/personal_assistant/gateway/composition.py:198-214`; `src/agent/sdk/kernel.py:229-334,571-590`; `src/agent/platform/hooks/builtins/auto_mode_gate.py:943-953` | E2E `tests/e2e/critical_paths/test_tool_approval_model_critical_path.py:221-261` 断言 A→C→A / B→C→B | covered |
| Web IM/外部渠道/heartbeat/cron/Agent 派生运行均使用 C | Kernel 唯一 registry 上的选择由同一 classifier 入口读取，不按 origin 变更 model：`src/agent/sdk/kernel.py:571-590`; `src/agent/platform/hooks/builtins/auto_mode_gate.py:943-953` | `tests/unit/test_auto_mode_gate_hook.py:209-227` 使用真实 `user/heartbeat/cron/background_task` 枚举值；E2E 补充真 Web IM | covered |
| 专用模型不改变 Agent 对话和工具后续模型 | 仅 stage 1/2 `call_model` 收到显式 model：`src/agent/platform/hooks/builtins/auto_mode_gate.py:436-542`；normal run 仍由 submit model 选择 | `tests/contract/test_sdk_kernel_wiring.py:257-331` 通过公开 SDK 断言 provider-a/A → provider-c/C → provider-a/A；E2E 再从产品入口断言 | covered |
| 省略专用模型时复用各 Agent 模型 | `src/personal_assistant/config/local_store.py:1012-1019`; `src/agent/platform/hooks/tool_approval_model.py:13-35`; `src/agent/core/agent/runtime.py:1480-1513` | config/hook unit tests + E2E `tests/e2e/critical_paths/test_tool_approval_model_critical_path.py:266-283` 断言 A→A→A / B→B→B | covered |
| 未注册审批模型拒绝 Gateway 启动 | PA catalog 校验 `src/personal_assistant/config/local_store.py:1071-1088`；SDK 通用不变量 `src/agent/sdk/kernel.py:295-334` | config unit、SDK contract 与 foreground E2E `:319-345` 均覆盖错误字段/错误值 | covered |
| 专用模型失败时不换 Agent/其他模型 | auto gate 超时/例外/不可解析直接形成 ask：`src/agent/platform/hooks/builtins/auto_mode_gate.py:470-542,993-1011`；runtime 单次按显式 model 选 client：`src/agent/core/agent/runtime.py:1480-1513` | unit 失败/无人值守用例 + attended E2E `:286-316`，record 中只有 `approval-fail` classifier | covered |
| C→D 配置修改重启后才生效 | `compose_gateway` 每进程读取一次，SDK build 写一次 registry：`src/personal_assistant/gateway/composition.py:198-214`; `src/agent/sdk/kernel.py:571-590` | E2E `tests/e2e/critical_paths/test_tool_approval_model_critical_path.py:240-261` 断言改盘未重启仍 C，restart/reconnect 后 D | covered |

## Prior Issue Closure

| Issue | 闭环证据 | 结论 |
|---|---|---|
| Round 1 W1：跨 provider client 路由未真正测到 | `tests/contract/test_sdk_kernel_wiring.py:257-331` 取消单 client override，由 factory 产生 provider-a/provider-c 独立 client，并断言 `(provider, model)` 序列 | closed |
| Round 1 W2：测试误用 `subagent` origin | `tests/unit/test_auto_mode_gate_hook.py:209-227` 改为生产枚举真值 `background_task` | closed |
| Round 1 S1：SDK 公开失败契约缺 `Raises` | `src/agent/sdk/kernel.py:248-294` 完整说明 llm 缺失、空值和未注册的 `ValueError` | closed |
| Code review：既有 `_classify_action(ctx, sys, user)` 直接调用因新 required kwarg 回归 | `src/agent/platform/hooks/builtins/auto_mode_gate.py:436-442` 给 model 保留 `None` 默认；`tests/unit/test_auto_mode_gate.py:365-405` 三条既有直接调用在本轮全部通过 | closed |
| Code review：dispatch hook harness 没有 registry-state getter | `tests/unit/test_auto_mode_gate_dispatch.py:57-71` 的 MockHooks 提供 `get_state`；全部 `test_auto_mode_gate*.py` 在 134-test 矩阵中通过 | closed |

## Coherence

| design 决策 | 遵守? | 证据 |
|---|---|---|
| D1 PA-owned optional config + parse/save/validate | 是 | `src/personal_assistant/config/local_store.py:48-64,900-931,996-1088` |
| D2 产品中立 SDK build 参数，不污染 `LLMConfig` | 是 | `src/agent/sdk/kernel.py:229-334`; `src/personal_assistant/product.py:381-431` |
| D3 唯一 registry-state bridge，不放 session metadata，不与 476 bundle 并存 | 是 | `src/agent/platform/hooks/tool_approval_model.py:1-35`; `src/agent/sdk/kernel.py:535-590`；source 中无 `BuiltinHookDependencies`，getter 的唯一生产 caller 为 auto gate |
| D4 两阶段 classifier 一致显式路由，normal run 不变 | 是 | `src/agent/platform/hooks/builtins/auto_mode_gate.py:436-542,943-953`; SDK contract A→C→A |
| D5 fail-closed 且不改选模型 | 是 | `src/agent/platform/hooks/builtins/auto_mode_gate.py:470-542,993-1011`; failure E2E |
| D6 仅 Gateway restart 切换 | 是 | `src/personal_assistant/gateway/composition.py:198-214`; restart E2E |
| D7 请求体 model 为确定性锚 | 是 | `scripts/fixtures/anthropic_sse_tool_approval_recording.py:135-173`; critical-path records |

架构自洽复核：无新的依赖方向、跨进程边界或平行机制。PA 仍只通过 `agent.sdk` 传递选择，`platform → core`、`sdk → core + platform` 保持；边界 contract 在本轮 134-test 矩阵中通过。

### Prototype / Reference Contract

N/A.

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.

## Corrected Delta Reconciliation

> Validation snapshot: `eaaed4c3ec91c5359044ca6b47d3834e8388063f → ea96d9d5a43a54ed22629066bae7ff523f6e347d`
>
> Validated at: `2026-08-06T19:00:29+08:00`
>
> Mode: `corrected-delta`（仅核对三份 active delta-spec 与最终可观察实现；不重复 full verification）

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `kernel/sdk-boundary` MODIFIED：装配与会话分层、内核产品中立 | `src/agent/sdk/kernel.py:229-313` 仅在产品中立的 `build_kernel` 增加 build-scoped 参数；PA 经 `agent.sdk` 传递，未增加产品分支 | Round 2 的 SDK/边界 contract 纳入 134-test 矩阵 | aligned |
| 应用零前置调用直接装配 | `src/agent/sdk/kernel.py:295-313,337-345` 仍由 `build_kernel` 负责 registry 初始化 | `tests/contract/test_sdk_kernel_wiring.py:229-237` | aligned |
| 三类应用对内核同构 | 参数属于通用 SDK surface；PA 仅在 `src/personal_assistant/product.py:381-438` 消费，无 PA 分支进入内核 | `tests/contract/test_agent_sdk_boundary_contract.py:35-63` | aligned |
| 工具目录共享、会话选子集 | 本 unit 未改变 tools catalog / `create_session(enabled_tools=...)` 路径 | Round 2 的 SDK behavior/架构 contract 纳入 134-test 矩阵 | aligned |
| Kernel 稳定对外方法集 | 本 unit 只扩展 `build_kernel` 参数，未改变 `Kernel` 方法集 | Round 2 的 SDK surface/behavior contract 纳入 134-test 矩阵 | aligned |
| 消费者选择已注册分类模型 | `src/agent/sdk/kernel.py:316-334,587-590` 校验 catalog 并写入单个 Kernel 的 hook registry | `tests/contract/test_sdk_kernel_wiring.py:257-331` | aligned |
| 消费者省略分类模型 | `src/agent/sdk/kernel.py:319-320,587-590` 保留 `None`；运行时据此复用当前 run model | `tests/unit/test_auto_mode_gate_hook.py:254-266`; E2E `tests/e2e/critical_paths/test_tool_approval_model_critical_path.py:267-283` | aligned |
| 消费者选择未注册分类模型 | `src/agent/sdk/kernel.py:295-334` 在 `_build_kernel_base` 创建 runtime / 后台任务前拒绝装配 | `tests/contract/test_sdk_kernel_wiring.py:239-241` | aligned |
| `kernel/runs` ADDED：分类可用消费者指定模型且不静默降级 | `src/agent/platform/hooks/tool_approval_model.py:10-35` 保存 build-scoped 选择；`auto_mode_gate.py:436-542,943-953` 仅向两阶段 classifier 传递该选择 | classifier unit、SDK contract 与真栈 E2E 均有永久覆盖 | aligned |
| 显式模型只用于自动分类 | classifier 两阶段显式用 C；普通 run 仍由 `src/agent/core/agent/runtime.py:1480-1513` 的 run model 路由 | `tests/contract/test_sdk_kernel_wiring.py:257-331` 断言 provider-a/A → provider-c/C → provider-a/A | aligned |
| 未显式选择时复用当前 run 模型 | gate 传 `model=None`，`runtime.py:1489-1493` 回落当前 run model | `tests/unit/test_auto_mode_gate_hook.py:254-266`; E2E `:267-283` | aligned |
| 显式模型必须属于 catalog | SDK 通用校验点名无效模型并拒绝 build | `tests/contract/test_sdk_kernel_wiring.py:239-241`; E2E `:320-345` | aligned |
| 显式模型失败不改用 run / 其他模型 | `auto_mode_gate.py:470-548,992-1011` 将失败/超时/不可解析转既有 ask；`runtime.py:1497-1513` 只向所选 client 发起该次调用 | `tests/unit/test_auto_mode_gate_hook.py:269-287`; E2E `:287-316` 只记录 `approval-fail` classifier | aligned |
| `gateway/agent-capabilities` ADDED：Gateway 可统一选择分类模型 | `local_store.py:48-64,996-1019,1071-1088` 定义/解析/校验 PA-owned 字段；`composition.py:194-216` 启动时一次性传入 Kernel | PA config/composition unit + 真栈 E2E | aligned |
| 不同 Agent / PA 运行来源共用 C，正常运行保留 A/B | Kernel-scoped registry 选择由唯一 classifier 读取且不按 origin 分支 | `tests/unit/test_auto_mode_gate_hook.py:209-227` 覆盖 `user/heartbeat/cron/background_task`; E2E `:222-261` 断言 A→C→A / B→C→B | aligned |
| Gateway 省略字段时各 Agent 复用自己的模型 | `local_store.py:1012-1019` 产生 `None`，Gateway 正常装配 | E2E `tests/e2e/critical_paths/test_tool_approval_model_critical_path.py:267-283` 断言 A→A→A / B→B→B | aligned |
| Gateway 配置未注册模型时拒绝启动 | `local_store.py:1071-1088` 在 Gateway 组合前拒绝配置并点名 `llm.tool_approval_model` | config unit `tests/unit/personal_assistant/config/test_parse_llm.py:76-87`; E2E `:320-345` | aligned |
| 专用分类模型失败后不改用 Agent 模型 | 两阶段失败进入既有 attended 审批或 unattended fallback，没有备用模型调用 | `tests/unit/test_auto_mode_gate_hook.py:269-287`; E2E `:287-316` | aligned |
| 修改选择后重启才生效 | `composition.py:194-216` 每个 Gateway 进程读取一次配置；registry state 无热更新入口 | E2E `tests/e2e/critical_paths/test_tool_approval_model_critical_path.py:222-261` 断言改盘仍 C、重启后 D | aligned |

### Uncovered Observable Behavior

None. 最终 diff 中其余变更为测试 fixture、运维说明、兼容既有直接调用的默认参数及验收报告，不新增未由三份 delta 描述的产品或 SDK 可观察行为。`7f0d4be1e3d2adf992dd80413a4bed587cbf5ff8` 之后仅 verification/acceptance 文档变化，因此 Round 2 在相同实现树上的永久测试证据仍适用于当前 HEAD。

Outcome: `aligned`
