# Verification Report: refactor-387

> Round: 1 | Mode: full | Branch: unit/refactor-387

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 12/13（M4 tasks.md R3 标记 TODO，实际代码已完成，文档笔误） |
| Correctness | 全部 Requirement 有实现路径；1 个 spec 定义与实现存在签名偏差 |
| Coherence | 整体遵守；1 处 SDK 表面宽度超出 design.md 定义范围，标注为 WARNING |

No critical issues. 2 warning(s) to consider. Ready for PR (with noted improvements).

---

## Completeness

### Task 完成检查

| Milestone | Roadpoints 完成情况 | 注意 |
|---|---|---|
| M1 sdk-and-llm-di | R1/R2/R3/R4 全 DONE（退出标准全 ✓） | — |
| M2 coding-cli-on-sdk | R1–R6 全 DONE | — |
| M3 pa-gateway-on-sdk | R1–R5 全 DONE | — |
| M4 remove-http-and-cleanup | R1/R2/R4/R5 DONE；R3 标记 TODO | 笔误（见下） |

**M4-R3 笔误**：`tasks.md` 第 35 行把 R3（删 `agent/platform/http_api/` 整目录）标为 TODO，但代码和 progress.md 均显示该目录已在 commit `4acede07` 中删除，`test_http_api_dir_removed.py` 绿。这是文档遗留笔误，不影响实现完成度。

总体计算：13 个 roadpoints，实际完成 13 个，tasks.md 标记 12 个（1 个标记与实际不符）。

**退出标准核查（M4）**

- [x] `agent/platform/http_api/` 目录已删除，无 `.py` 源文件（`rglob("*.py") == []`，免疫 `__pycache__` 残留）
- [x] `EventStreamHub` / `StreamEvent` / `SubscriberOverflowError` 迁到 `agent/core/events/`（`src/agent/core/events/hub.py:4`）
- [x] `coding_cli/{client,kernel_app,managed_server,session_stream}.py` 及专属测试已删除
- [x] 全量测试全绿，零 failed，零 xfail（本地验证：2332 passed, 0 failed, 0 xfail）
- [x] `test_spec_declares_sdk_only_boundary_rules` 绿（SPEC.md 新边界原文，`tests/contract/test_cli_http_only_contract.py:133`）
- [x] `test_architecture_docs_describe_zero_residue_target_state` 绿（`tests/contract/test_multi_product_architecture_acceptance.py:141`）
- [x] `test_top_level_packages_keep_zero_import_boundaries` 去 xfail 后绿（Closes #39）

### Spec Requirement 覆盖

| Requirement | 实现路径 | 覆盖状态 |
|---|---|---|
| coding_cli 多步工具调用 agent 任务正常完成 | `coding_cli/commands.py` async REPL + `agent.sdk.build_kernel` 进程内执行 | covered（Review-A 通过） |
| personal_assistant 经 IM/channel 的工具型任务保持一致 | `personal_assistant/main.py:1390` + `gateway/inbound_pipeline.py` SDK 调用 | covered（Review-B 通过） |
| gateway 运维命令保持可用（stop/restart） | `personal_assistant/main.py` 内核进程内化，无独立 kernel 子进程 | covered |
| LLM provider 选择与调用保持一致（#40） | `agent/platform/llm/factory.py` 持具体 client，`core/llm/factory.py` 零 platform import | covered |

---

## Correctness

### Requirement 实现映射

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 多步工具调用完成真实编码任务 | `coding_cli/commands.py:253` `_build_kernel` + async REPL | Review-A 通过 | covered |
| 工具权限确认（can_use_tool 回调） | `agent/sdk/kernel.py:531` `_make_permission_requester` | `tests/contract/test_agent_sdk_surface_contract.py` | covered |
| 任务执行中途打断 | `agent/sdk/kernel.py:368` `interrupt()` + `cancel_all_pending` | `tests/contract/test_agent_sdk_surface_contract.py` | covered |
| 后台任务完成通知 | `EventStreamHub` 持久 session 流；run 结束不关闭流 | `tests/contract/test_kernel_sdk_behavior_contract.py` | covered |
| 子 agent / task 工具 | 复用既有 task tool，不受 HTTP 删除影响 | task tool 单测 | covered |
| skill 调用 | `build_kernel` 中 `build_hook_registry` 复用既有 skill hook | skill 单测 | covered |
| REPL 内置命令 `/compact` `/tools` 等 | `coding_cli/input/repl_commands.py` | `tests/contract/test_cli_http_only_contract.py:174` | covered |
| 无模式直接进入 REPL | `coding_cli/main.py` `asyncio.run(repl_main())`，无 `--mode`/`--base-url` | `test_cli_has_no_mode_flag` | covered |
| 经 IM 完成含工具调用任务 | `gateway/inbound_pipeline.py` `await kernel.submit/stream` | Review-B 通过 | covered |
| heartbeat/cron 触发工具型任务 | `personal_assistant/main.py` 持 Kernel 实例，heartbeat 经同一 Kernel | PA 单测 | covered |
| gateway stop/restart 无残留 kernel 子进程 | `main.py` 删 spawn/killpg；内核随 gateway 生命周期 | `test_personal_assistant_main_contract.py` | covered |
| anthropic / openai_compat provider 正常应答 | `agent/platform/llm/factory.py` `_PROVIDER_CLIENTS` | `test_llm_provider_contract.py` | covered |
| 不支持 provider 报错 | `platform/llm/factory.py:57` `ValueError: unsupported llm provider` | `test_llm_provider_contract.py` | covered |
| #39 Closes：产品只 import agent.sdk | `test_top_level_packages_keep_zero_import_boundaries`（无 xfail） | contract test | covered |
| #40 Closes：core 零 platform import | `test_core_no_platform_imports.py`（无 xfail），`core/llm/factory.py` 无 platform import | contract test | covered |

**WARNING-1：`build_kernel` 签名与 design.md 定义不一致**

`design.md:118` 定义：
```python
build_kernel(*, product_profile, llm_config: LLMConfigPayload, ...)
```
实现（`agent/sdk/kernel.py:67-76`）：
```python
build_kernel(*, product_profile, llm_config: LLMFactoryConfig, ...)
```
两者语义不同：`LLMConfigPayload` 是含 providers/models 列表的完整 Gateway config wire schema（`agent/core/llm/config.py:33`）；`LLMFactoryConfig` 是已解析的单一 provider+model+endpoint 运行时配置（`agent/core/llm/factory.py:22`）。

实现路径是：PA 在调用 `build_kernel` 前先显式调用 `init_model_registry(config.llm)` 初始化全局 registry，再调 `LLMFactoryConfig.from_env()` 解析当前 provider，再传给 `build_kernel`（`personal_assistant/main.py:1098,1403-1408`）。design.md 预期 `build_kernel` 自己接受 `LLMConfigPayload` 并内部处理 init_model_registry，但实现把这两步分离到调用者。

功能上两条路径等价，且实测通过。但这与 design.md 接口定义不一致。

---

## Coherence

### design.md 关键决策遵守检查

| 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策 1: SDK 落在顶层 `agent/sdk/`（第 4 层），删 `agent/platform/sdk/client.py` | 是 | `src/agent/sdk/` 存在；`agent/platform/sdk/` 只剩空 stub `__init__.py`（明确标注 legacy stub，注释说明将删除） |
| 决策 2: 内核单一 async `Kernel`；两个消费方都 async-native | 是 | `coding_cli/main.py` `asyncio.run(repl_main())`；`personal_assistant` async gateway；`Kernel` 全 async-native，无 SyncKernel |
| 决策 3: 权限统一为 `can_use_tool` 回调，删除 `permission_request` 事件+resolve 旁路 | 是 | `agent/sdk/kernel.py:531` `_make_permission_requester`；permission_request 事件路径仅在旧 HTTP 路由中存在，已随 http_api 删除 |
| 决策 4: DI 注入 `LLMClientFactory`，core 只持 `LLMClient` 端口 | 是 | `core/llm/factory.py` 只含 `LLMFactoryConfig` dataclass；`platform/llm/factory.py` 持 `_PROVIDER_CLIENTS`；`AgentRuntime.__init__` 接受 `llm_client_factory` 参数（`runtime.py:85`） |
| `test_core_no_platform_imports.py` 去 xfail 转常规守卫 | 是 | 文件无 xfail，2332 passed 中包含此测试 |
| `test_cli_http_only_contract.py` 改写为「产品只 import agent.sdk」边界检查，去 xfail | 是 | `test_cli_http_only_contract.py:118` 硬断言，无 xfail |
| `scripts/e2e-up.sh` 去「起 Kernel API」段 | 是 | `e2e-up.sh:136` 注释说明 kernel 已进程内，无独立 API 段 |

**WARNING-2（orchestrator 标注疑点）：`agent.sdk` 公开表面含内部实现细节**

`agent/sdk/__init__.py` 的 `__all__` 共 20 个导出，其中以下 7 个是 core/platform 内部实现细节，在 `design.md` 的「接口与数据流 → agent.sdk 对外表面」定义中**未列出**：

- `SkillRegistry`（`agent/core/skills/registry.py:19`）— skill 发现/缓存的内部实现类
- `ConfigResolver`（`agent/platform/config/resolver.py:22`）— platform 层路径解析工具
- `FEATURE_REGISTRY`（`agent/core/agent/prompt_sections/feature_registry.py:49`）— 提示词 section 注册表，纯内部数据
- `default_skill_search_roots`（`agent/core/skills/discovery.py`）— 内部路径发现函数
- `init_model_registry`, `get_default_model`, `get_default_provider`, `list_provider_models`, `list_supported_providers`（`agent/core/llm/model_registry.py`）— LLM registry 操作函数

**根因**：M4-R5 为让 `personal_assistant/reporter/upstream_reporter.py` 遵守「只 import agent.sdk」规则，将它原本直接 import `agent.core.*` / `agent.platform.*` 的 7 个符号全部经 `agent.sdk` re-export（`upstream_reporter.py:9-18`，`main.py:30`）。这是「绕开边界规则而不是真正尊重它」的做法——SDK 成了 internal passthrough 而不是 curated surface。

**评估**：

- **不影响功能正确性**，所有测试通过
- **违反 design.md 的 SDK 设计原则**：design.md「决策 1」明确 SDK 是「最干净可被 AST 守卫直接断言」的对外面；contract test `test_agent_sdk_boundary_contract.py` 已断言产品只 import `agent.sdk`，但没有断言 SDK 表面的宽度——边界守卫对 passthrough re-export 无感
- **建议严重度：WARNING**（功能正确，但 SDK 的「curated surface」语义受损；不阻 PR，但值得在下一个 unit 修整）

**建议修复方向（不阻本 PR）**：
1. `upstream_reporter.py` 中对 `SkillRegistry`, `ConfigResolver`, `FEATURE_REGISTRY` 的使用，可以在 PA 内部新建一个薄的能力发现适配器（如 `personal_assistant/capabilities.py`），在 `agent.sdk` 中只 export 该适配器需要的最终聚合结果（如 `build_node_capabilities() -> dict`），而不是 export 原始内部类
2. 5 个 LLM model registry 函数（`init_model_registry` 等）若 PA 必须用，至少属于「可发布工具函数」，比 `SkillRegistry` / `ConfigResolver` / `FEATURE_REGISTRY` 更接近合理的 SDK 表面；可接受为 SDK 扩展面保留
3. 在 `agent/sdk/__init__.py` 的 docstring 中，当前已分为「Core kernel assembly」和「Extended surface for personal_assistant (reporter / upstream_reporter)」两段，意图是好的，但缺少明确的设计约束说明——建议加 comment 标注哪些是「acceptable extension」，哪些是「待收敛的临时 passthrough」

---

## Issues

### WARNING

**W1：`build_kernel` 实参类型与 design.md 接口定义不一致**

- 文件：`src/agent/sdk/kernel.py:70`
- design.md 第 118 行：`llm_config: LLMConfigPayload`
- 实现：`llm_config: LLMFactoryConfig`
- 影响：API contract 与 design 不同步；调用者（PA `main.py:1404`）需在外部额外调用 `init_model_registry` + `LLMFactoryConfig.from_env()` 两步，而 design 预期 `build_kernel` 自己处理
- 修复建议：要么将 design.md 第 118 行更新为 `llm_config: LLMFactoryConfig`（承认简化是正确的），要么将 `build_kernel` 改为接受 `LLMConfigPayload` 并内部调用 `init_model_registry(payload)` + 解析。前者工作量小，且实现经过 reviewer 验证，更推荐。

**W2：`agent.sdk` 公开表面含 7 个未在 design.md 中定义的内部类 re-export（orchestrator 标注疑点）**

- 文件：`src/agent/sdk/__init__.py:42-47`（SkillRegistry, ConfigResolver, FEATURE_REGISTRY, default_skill_search_roots 导出行）
- 根本路径：`upstream_reporter.py:9-18` 为遵守「只 import agent.sdk」规则，促使 M4-R5 将 7 个内部符号经 SDK re-export
- 影响：SDK 「curated surface」语义受损，变成 internal passthrough；未来 SDK 演进时这些内部符号会带来约束
- 修复建议（不阻本 PR，下一轮 unit 处理）：在 PA 层引入能力适配器 `personal_assistant/capabilities.py`，将 `build_node_capabilities_payload` / `build_agent_capabilities_payload` 等函数内聚到 PA 自身，通过 `build_kernel` 参数（如返回的 `Kernel` 增加 `list_skills()` 方法）或 `PERSONAL_ASSISTANT_PROFILE` 获取 PA 特有信息，而不是 export 内部实现类到 SDK 表面。

### SUGGESTION

**S1：M4-R3 tasks.md 状态标记笔误**

- 文件：`docs/changes/refactor-387-kernel-sdk-no-http-api/M4-remove-http-and-cleanup/tasks.md:35`
- 现状：`R3 | 删 agent/platform/http_api/ 整目录 | TODO`；实际已完成（commit `4acede07`）
- 修复：将 R3 状态改为 DONE

**S2：遗留空目录和过时 docstring**

- `src/personal_assistant/client/__init__.py:1`：docstring 写 "HTTP clients used by the personal assistant gateway"，但 `kernel_api_client.py` 已删，目录只剩 `__init__.py`；要么删除空目录，要么更新 docstring
- `src/agent/platform/sdk/__init__.py`：stub 注释说「This __init__.py is left empty…will be removed in M4」，但 M4 已结束未删；建议补删或保留时删掉 "will be removed in M4" 的说法

---

## 结论

No critical issues. 2 warning(s) to consider. Ready for PR (with noted improvements).

- W1（build_kernel 签名偏差）：功能正确，建议在 PR description 中说明此处与 design.md 的意图偏差，或同步更新 design.md
- W2（SDK 表面过宽）：是 orchestrator 标注疑点的结论——当前实现选择了「扩 SDK 表面 re-export 内部类」而不是「收敛 PA 的能力报告逻辑」，SDK 的「curated surface」属性受损，建议作为后续 unit 的改进项立 issue 追踪

---

# Round 3

> Branch HEAD: 97df54a7 | 变更：sdk-fix-r3（Kernel.stream() 扁平 dict + ContextVar 修复）

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 继承 Round 1 结论（全部 tasks 完成） |
| Correctness | sdk-fix-r3 三项变更全部正确实现；1 个 pre-existing warning 仍存在（非本修复引入） |
| Coherence | 变更方向与 Round 1 W2 关切一致；Round 1 W1 已通过 design.md Changelog 记录 |

No critical issues. 1 warning(s) to note (pre-existing). All checks passed. Ready for PR.

---

## Round 3 变更核查

### 变更 1：`Kernel.stream()` 改为产出扁平 dict（`_stream_flat`）

**实现**（`src/agent/sdk/kernel.py:345-389`）：

- `stream()` 签名改为 `-> AsyncIterator[dict[str, Any]]`，通过 `return self._stream_flat(...)` 委托
- `_stream_flat` 为 async generator，`async for ev in event_hub.stream_session(...)` 遍历 `StreamEvent`，将 `ev.data` 展开为顶层，并 `setdefault("event", ev.event)` / `setdefault("session_id", ...)` / `setdefault("sequence_num", ...)`
- `StreamEvent` 不再出现在 SDK `__init__.py` 的 `__all__` 中，不泄漏到公开表面

**评估**：

- 消费方（`async for event in kernel.stream(...)`）可以直接 `event.get("run_id")`、`event.get("event")` 等，不需要知道 `StreamEvent` 的内部结构
- 这比 Round 1 时 `stream()` 返回 `AsyncIterator[StreamEvent]`（内部类泄漏）更干净——直接响应了 W2「SDK curated surface」的关切方向
- dict 展开逻辑：`flat = dict(ev.data); flat.setdefault("event", ev.event); ...`——当 `ev.data` 中已包含 `event` 字段时 setdefault 保留原值，不冲突；当不包含时从 `ev.event` 补全。语义正确

**结论**：covered，正确

### 变更 2：PA `_stream_event_to_dict` 局部补丁删除

**实现**（`src/personal_assistant/gateway/inbound_pipeline.py:889-919`）：

- `_KernelStreamAdapter.stream_session()` 直接 `async for event in self._kernel.stream(...): yield event`
- `_stream_event_to_dict` helper 已删除，`_KernelStreamAdapter` 不再做任何 normalization
- 上游真实 `Kernel.stream()` 已产出 flat dict，所以不需要补丁

**评估**：正确。M3-fix-r2 的局部补丁（`_stream_event_to_dict`）是当时 `stream()` 返回 `StreamEvent` 的临时适配；现在 stream() 改为 dict 后，该补丁正确删除

**结论**：covered，正确

### 变更 3：`RunsRegistry.submit()` ContextVar 修复

**实现**（`src/agent/core/runs/registry.py:168-177`）：

```python
ctx = contextvars.copy_context()
self._async_loop.call_soon_threadsafe(
    lambda: self._async_loop.create_task(coro, context=ctx)
)
```

**设计正确性分析**：

1. **线程安全**：`call_soon_threadsafe` 是 Python asyncio 文档中唯一推荐的跨线程安全调度原语（内部持有 lock），正确
2. **Context 传播**：`copy_context()` 在 submit() 时（caller 线程）创建当前 Context 的快照；`create_task(coro, context=ctx)` 使 Task 在该快照 Context 里运行；`bind_correlation` 里 `_context.set(current)` 和 `_context.reset(token)` 都在同一 `ctx` 里执行，不会触发 `ValueError: token was created in a different Context`
3. **原理验证**（本地测试）：`copy_context()` + `create_task(context=ctx)` 模式对所有 ContextVar（包括 `_span_stack`）均正确，在 ctx 内 set/reset 正常工作

**测试覆盖**：

- 2334 passed（Round 1 的 2332 + 2 个新测试），0 failed，0 xfail
- `tests/contract/test_kernel_sdk_behavior_contract.py` 8 passed（含 `test_llm_config_reconfigure_updates_provider`）

**残留 warning**：

`test_llm_config_reconfigure_updates_provider` 仍触发 `PytestUnraisableExceptionWarning`，内容为 `_span_stack`（非 `_context`）ContextVar 的 token 错误。

- 这个 warning 在 Round 1 测试中已存在（同一测试文件）
- 触发路径：`hook observe dispatch` 内部的 `span()` 调用，不在 `_run_worker_async` 主路径上
- 修复正确处理了 `bind_correlation`（`_context`）的问题；`_span_stack` 在 hook dispatch 路径的类似问题是 **pre-existing**，超出本修复范围
- 功能测试全部通过（8/8 pass），warning 不影响正确性

**结论**：ContextVar 修复本身正确；`_span_stack` warning 属 pre-existing，不阻 PR

---

## Round 1 未关闭项状态

| 问题 | 本轮状态 |
|---|---|
| W1：`build_kernel` 签名与 design.md 不一致 | 已通过 design.md Changelog（第 9 行）记录，说明此为功能等价的有意简化，关闭 |
| W2：SDK 表面含内部类 re-export | 维持 follow-up issue 建议不阻 PR；`StreamEvent` 不再在 SDK 表面（`stream()` 改为返回 `dict`），部分改善；`SkillRegistry`/`ConfigResolver`/`FEATURE_REGISTRY` 等 re-export 仍在，待后续 unit 处理 |
| S1：M4-R3 tasks.md TODO 笔误 | 仍未修（非阻 PR 项） |
| S2：遗留空目录/过时 docstring | 仍未修（非阻 PR 项） |

---

## Issues（Round 3 新增）

### WARNING

**W3（pre-existing）：`_span_stack` ContextVar 在 hook observe dispatch 路径仍有 token 错误 warning**

- 文件：`src/agent/core/observability/tracing.py:145`（`span()` 的 `_span_stack.set/reset`）
- 场景：`test_llm_config_reconfigure_updates_provider` 触发真实 run，hook observer 在不同 Context 里调用 `span()`，`_span_stack.reset(token)` 报 `ValueError`
- 注意：此问题在 Round 1 已存在，不是 sdk-fix-r3 引入
- 修复建议（不阻本 PR）：在 `_dispatch_observe_async`（`registry.py:408,469`）前也做 `copy_context()` 传播；或在 `span()` 的 finally 中捕获 `ValueError: token was created in a different Context` 并静默（若 hook dispatch 路径的 span 不是核心追踪路径）

---

## 结论（Round 3）

All checks passed. Ready for PR.

- Round 1 W1 已通过 design.md Changelog 关闭
- Round 1 W2 部分改善（StreamEvent 不再泄漏），残余 SkillRegistry/ConfigResolver/FEATURE_REGISTRY re-export 待后续 unit
- sdk-fix-r3 三项变更（stream 扁平化、PA 补丁删除、ContextVar 修复）均正确实现
- W3 为 pre-existing warning，不阻 PR

---

# Round 4

> Branch HEAD: 67d3645b | 重点：session 复用历史接续 fix 正确性核查 + agent system prompt preview 链路断裂根因判定

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 继承 Round 3（全量 2337 passed，0 failed） |
| Correctness | session 复用 fix 本身正确；2 个新问题：集成测试 stub 契约错位（WARNING）+ prompt preview in-unit 回归（CRITICAL） |
| Coherence | M3 "行为完全不变"声明与 prompt_preview_provider=None 矛盾，属于 in-unit 行为回归未记录 |

**2 critical issue(s) found. Fix before PR.**

---

## Round 4 重点核查

### 1. session 复用历史接续 fix（df319bee 等）

**fix 本身：正确**

- `Kernel.get_session`（`src/agent/sdk/kernel.py:515-549`）暴露顶层 `workspace_root`：从 `Session.workspace_root` 取，不经 metadata；注释明确说明"workspace_root is exposed as a top-level key so that _binding_matches_workspace_root can compare it directly"
- `_binding_matches_workspace_root`（`src/personal_assistant/gateway/inbound_pipeline.py:557-585`）读 `session_payload.get("workspace_root")` 而非 `metadata["workspace_root"]`，正确
- `tests/unit/personal_assistant/test_session_reuse_regression.py`：3 个测试（contract × get_session 顶层字段、binding_matches 读顶层、端对端 session 复用）全绿，回归测试有效覆盖根因路径

**残留缺口：WARNING（见 W4）**

`tests/im_service/integration/_gateway_helpers.py:89-93` 的 `_FakeKernel.get_session` 仍然返回缺少顶层 `workspace_root` 的 dict：

```python
# _gateway_helpers.py:89-93 — WRONG: workspace_root buried in metadata
def get_session(self, session_id: str, *, workspace_root: Any = None, **_kwargs) -> dict[str, Any]:
    metadata = self._session_metadata_by_id.get(session_id)
    if metadata is None:
        raise RuntimeError(f"missing session: {session_id}")
    return {"session_id": session_id, "status": "active", "created_at": "now", "metadata": dict(metadata)}
```

`create_session` 把 `workspace_root` 写进 `_session_metadata_by_id`（第82-85行），但 `get_session` 返回时只打包 `metadata` 字典，没有把 `workspace_root` 提到顶层——与 `Kernel.get_session` 的正确契约（顶层暴露）不符。

后果：在 IM 集成测试层，`_binding_matches_workspace_root` 每次都返回 False（workspace_root 检查失败），所有使用此 stub 的测试（`test_gateway_im_roundtrip.py`、`test_gateway_im_direct_chat.py`、`test_gateway_im_group_chat.py`、`test_group_chat_flow.py` 等）都无法验证 session reuse 路径。此问题不影响测试通过（测试只发一条消息，不断言 reuse），但留下测试盲区。

同样问题存在于 `tests/im_service/integration/_group_chat_helpers.py:123-124`（返回 `{"session_id", "status", "metadata": {}}` 无顶层 workspace_root）。

另注：`tests/unit/personal_assistant/_pipeline_helpers.py:72-76`（旧 `_FakeKernelClient`，非本 unit 核心，部分集成测试用别名导入）同一问题，但该 stub 主要用于测试 legacy session refresh 路径（刻意让 workspace check 失败），可保持现状，但需要文档说明。

### 2. agent system prompt preview 链路（前端 "Preview full system prompt" 按钮不显示）

**根因：in-unit 回归**

链路：前端 → `POST /im/v1/agents/{id}/prompt-preview` → `IM.api.routes.agents.agent_prompt_preview` → `gateway_handler.request_prompt_preview` → WebSocket → `im_connection.py:380-411 agent.prompt.preview.request` handler → `self._prompt_preview_provider`

M3 commit 9954e383 将 `prompt_preview_provider=None`（`src/personal_assistant/main.py:1493-1495`），注释"skip preview until a direct SDK method is available in a later milestone"。

当 `_prompt_preview_provider is None` 时（`im_connection.py:398-403`），Gateway 返回 `preview: {}`（空字典）给 IM，IM `routes/agents.py:452-455` 取 `result.get("prompt")` 得 `None`，返回 `PromptPreviewResponse(prompt="", section_count=0)`，前端显示空字符串。

**in-unit 判定依据**：

1. 旧实现（删除前）调用 `kernel_client.prompt_preview(...)`，该方法经由内核 HTTP `POST /v1/prompt-preview` 组装完整系统提示并返回。refactor-387 删除内核 HTTP API 时，直接将此调用链设为 None，未提供进程内替代
2. `kernel_client.prompt_preview` → `agent/platform/http_api/routes/session.py`（现已删除）这条路径是 refactor-387 主要删除对象
3. M3 `tasks.md:16` 声明"从外部（IM / channel 用户）看行为完全不变"，但 prompt preview 是 IM 设置页的功能，对 IM 用户可见，行为已改变（功能变为空响应）
4. design.md 的"删除"列表（`agent/platform/http_api/routes/`）包含 session routes，其中含 `prompt-preview` 端点实现；未有对应迁移说明

**SDK 层迁移路径（修复建议）**：

`Kernel` 已有 `build_kernel(product_profile, llm_config, ...)` + `agent/core/agent/prompting.py:build_system_prompt`。进程内 prompt preview 可通过直接调用 `build_system_prompt(prompt_context)` 实现，无需 HTTP roundtrip。具体：

```python
# personal_assistant/main.py 中，替换 prompt_preview_provider=None 为：
from agent.sdk.kernel import Kernel  # kernel 已在 build_runtime 中构建
from agent.products.personal_assistant.prompt_sections import build_pa_system_prompt
from agent.core.agent.prompting import build_system_prompt, PromptContext

def _build_prompt_preview_provider(kernel: Kernel):
    def preview(agent_id, workspace_root, features, custom_prompt, tool_ids, scenario, skill_ids):
        # 直接调用 build_system_prompt 而不是走 HTTP
        prompt_context = PromptContext(...)  # 从 features/custom_prompt/skill_ids 组装
        sections = build_pa_system_prompt()
        rendered = build_system_prompt(prompt_context, prompt_sections=sections)
        return {"prompt": rendered, "section_count": len(sections)}
    return preview
```

或：在 `Kernel` 上增加 `assemble_prompt_preview(features, custom_prompt, tool_ids, scenario, skill_ids, workspace_root)` 方法（SDK 扩展，与 session/submit/stream 对齐的 SDK surface）。

---

## Issues（Round 4 新增）

### CRITICAL

**C1：agent system prompt preview 功能因删除内核 HTTP API 而断裂（in-unit 回归）**

- 文件：`src/personal_assistant/main.py:1493-1495`
- 根因：M3 将 `prompt_preview_provider=None`，删除了 `kernel_client.prompt_preview(...)` 调用但没有提供进程内替代
- 影响：前端 agent 设置页 "Preview full system prompt" 按钮调用 `POST /im/v1/agents/{id}/prompt-preview` 返回 `{"prompt": "", "section_count": 0}`，用户无法预览完整系统提示
- 测试覆盖缺口：无任何测试断言 `prompt_preview_provider` 非 None 或 prompt preview 返回非空结果；`tests/im_service/` 中的 prompt preview 测试（若有）使用 mock，不覆盖 `main.py` 的 `None` 装配
- 修复建议：在 `build_runtime`（`main.py:~1437`）中替换 `prompt_preview_provider=None` 为调用 SDK 内部 `build_system_prompt` 的进程内实现；同时在 `build_runtime` 级别补充集成测试，断言 `prompt_preview_provider` 非 None 且调用后返回非空 prompt

### WARNING

**W4：`tests/im_service/integration/_gateway_helpers.py:_FakeKernel.get_session` 不符合修复后的 Kernel.get_session 契约**

- 文件：`tests/im_service/integration/_gateway_helpers.py:89-93`；同样存在于 `tests/im_service/integration/_group_chat_helpers.py:123-124`
- 根因：stub 的 `get_session` 返回 `{"session_id", "status", "created_at", "metadata"}` 无顶层 `workspace_root`，与 df319bee 修复后 `Kernel.get_session` 的契约（顶层暴露）不一致
- 影响：IM 集成测试中 `_binding_matches_workspace_root` 对 stub 始终返回 False，所有发送多条消息的集成测试都无法断言"第二条消息复用同一 session"。目前没有集成测试覆盖此场景，存在测试盲区
- 修复建议：
  1. 更新 `_gateway_helpers.py:_FakeKernel.get_session`：在返回 dict 中加顶层 `workspace_root: str`，从 `_session_metadata_by_id[session_id].get("workspace_root", "")` 取（第84行已存入）
  2. 更新 `_group_chat_helpers.py:_FakeKernel.get_session`：同样补充顶层 `workspace_root`，从已存的 `_sessions` 字典或 `_session_metadata_by_id` 取
  3. 在 `tests/im_service/integration/` 增加一个两消息连发的集成测试（发两条消息断言 `create_session_calls` 长度为 1），覆盖 session reuse 路径

---

## Round 3 未关闭项状态

| 问题 | 本轮状态 |
|---|---|
| W2：SDK 表面含内部类 re-export | 维持 follow-up issue，不阻 PR |
| S1：M4-R3 tasks.md TODO 笔误 | 仍未修 |
| S2：遗留空目录/过时 docstring | 仍未修 |
| W3：_span_stack ContextVar warning（pre-existing）| 仍存在，不阻 PR |

---

## 结论（Round 4）

**2 critical issue(s) found. Fix before PR.**

- C1（prompt_preview_provider=None）：in-unit 回归，删除内核 HTTP API 时未迁移 prompt preview 到 SDK，功能断裂对 IM 用户可见，必须修复后才能 PR
- W4（集成测试 stub 契约错位）：session reuse fix 本身正确，但 IM 集成测试的 FakeKernel stub 未同步更新，留下测试盲区；不阻 PR 但应在同一 fix milestone 补齐
