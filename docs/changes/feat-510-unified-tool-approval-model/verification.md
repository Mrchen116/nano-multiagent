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

