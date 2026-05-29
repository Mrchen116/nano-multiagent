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
