# Verification Report: refactor-406

> Branch: `unit/refactor-406` (HEAD 846b0c9c)  
> Round: 1  
> Verifier worktree: `.worktrees/verify-refactor-406`  
> Date: 2026-06-14

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 7/7 tasks (M1) + M2 all roadpoints DONE |
| Correctness | 全 delta-spec requirements/scenarios covered |
| Coherence | Followed（决策 1-12 全部遵守）|

No critical issues. 1 warning to consider. Ready for PR (with noted improvement).

---

# Round 2

> Branch: `unit/refactor-406` (HEAD 8a5c220b)  
> Fix commits: 262bcb63..8a5c220b (M3fix #1-#7)  
> Date: 2026-06-15

## Round 2 Summary

| 维度 | 结果 |
|---|---|
| fix diff 完整性 | 7 项 fix 全部实现 |
| 决策符合性 | 决策 2/4/8 遵守，无 ConfigResolver 复活，无 platform→sdk 倒挂 |
| 全树测试 | 2587 passed / 0 failed / 1 skipped，ruff 全绿 |

All checks passed. Ready for PR.

## Round 2 核查明细

### 核查范围

fix diff: commits 262bcb63..8a5c220b，共 5 commits（#1 工作区工具发现 + #4 SkillManageTool per-session / #2 tool/hook 部署根对称补全 / #3 preview skill resolver / #5 self_evolution re-home / #6 CLI skill_search_roots / #7 close_session 内存清理）。

### 决策 2：工作区 .nano/tools 运行时发现（#1 恢复）

`sdk/kernel.py:464`：`load_tools_from_directory(repo_root=resolved_repo_root, registry=tool_registry)` 在注册内置工具 + 显式 `tools=` 后立即调用，扫描 `<repo_root>/.nano/tools`，不经 ConfigResolver。顺序：builtins → tools= → workspace .nano/tools → tool_search_roots 部署根——与决策 2「.nano/tools 运行时发现不变」一致。

### 决策 2：tool_search_roots / hook_search_roots 入参（#2）

`_SearchRootsResolver`（`sdk/kernel.py:266-296`）鸭子满足 loader 私有 Protocol `_ToolRootResolver`（`user_tool_roots()`）和 `_HookRootResolver`（`user_hook_roots()`），workspace `.nano/{tools,hooks}` FIRST 再 extra_roots，去重保序。无 ConfigResolver 继承，无 sdk import。consumer 工厂（`coding_cli/product.py:CLI_TOOL/HOOK_SEARCH_ROOTS`、`personal_assistant/product.py:PA_TOOL/HOOK_SEARCH_ROOTS`）显式传入，port 自旧 LOCAL_CODING_PROFILE/ConfigResolver user_tool/hook_roots()。delta-spec 签名行已同步补 `tool_search_roots=() / hook_search_roots=()`。

### 决策 8：preview per-call skill resolver（#3）

`sdk/kernel.py:1397-1408`：`assemble_prompt_preview` 中 skill_ids 解析改为新建 `_WorkspaceDirnameSkillResolver(workspace_root=effective_root, workspace_config_dirname=..., extra_roots=self._skill_search_roots)`，与 `list_skills` 同源——去除了原来读取 `runtime._config_resolver`（2 层路径恒 None → skill 段空白）的 bug。预览=真实会话同源（决策 8）。

### SkillManageTool per-session 派生（#4）

`platform/tools/builtins/skill_manage.py`：`__init__` 新增 `workspace_config_dirname` / `extra_roots` 路径（固定 `skill_root+registry` 路径保留向后兼容测试）；`run()` 调 `_resolve_writer_registry(ctx)` 从 `ctx.session_metadata["workspace_root"]` + `workspace_config_dirname` per-call 派生 writer+registry，search_roots = [write_root] + extra_roots 去重，与 `Kernel.list_skills` 同逻辑（决策 4 一致）。**零 sdk import**（只 import `agent.core.skills.registry`/`writer`），无 platform→sdk 倒挂。

### self_evolution config re-home（#5）

`sdk/kernel.py:587-634`（`_load_self_evolution_config`）+ `kernel.py:729-750`（`create_session`）：仅用 `effective_root / workspace_config_dirname / "config.yaml"` 定位文件（无 ConfigResolver / user roots），port 原 bootstrap._load_self_evolution_config 逻辑 + fallback；caller-supplied metadata 胜出（不覆盖显式值）。新测试 `tests/unit/agent/test_kernel_self_evolution_metadata.py` 4 passed。

### CLI skill_search_roots 补全（#6）

`coding_cli/product.py:CLI_SKILL_SEARCH_ROOTS = (~/.nanocode/skills, ~/.codex/skills)`，port 自旧 LOCAL_CODING_PROFILE。M2 只补了 PA，漏了 CLI——此 fix 对称。

### close_session 内存清理（#7）

`agent/core/agent/runtime.py:1051`：`self._session_prompt_slots.pop(session_id, None)` 在 `close_session` 中清理 PromptSlots 映射，消除本 unit 引入的长会话 churn 内存泄漏。新测试 `tests/unit/test_runtime_close_session_prompt_slots.py` 1 passed。

### Round 1 WARNING W1 状态

`docs/specs/kernel/spec.md`（canonical）仍未归并 delta-spec（旧 API 描述保留）。本次 fix diff 未处理。**仍为 WARNING**，不影响 PR merge，建议后续 roadpoint 归并。

---

## Completeness

### M1 Tasks（7/7 完成）

全部退出标准 `[x]`：

| # | Task | 状态 |
|---|---|---|
| 1 | `build_kernel` 2 层入口 + `create_session` per-agent + `list_*` 单测 | `[x]` |
| 2 | 外部产品最小证明（包外仅经 agent.sdk 装配 + 工具调用一轮） | `[x]` |
| 3 | PA/LC 完整 system prompt 重构前后逐字节等价 | `[x]` |
| 4 | cron 段逐字节 golden 先行 | `[x]` |
| 5 | sdk/prompt/llm/cron/dto 旧导出清零（除 `_M1_TEMP`）、HostCapabilityDispatcher 删除 | `[x]` |
| 6 | 决策 7 守卫脚手架立（3 道闸绿） | `[x]` |
| 7 | `coding_cli` 仅 import 新表面；全测试树 not-e2e 全绿 | `[x]` |

### M2 Roadpoints（全 DONE）

M2 无单独 tasks.md，进度由 `M2-gateway-capability/progress.md` 记录：

| Roadpoint | 状态 |
|---|---|
| R1 capability payload 基线 fixture | DONE (commit 3fede227) |
| R2 reporter 数据源换 kernel.list_* + Gateway 投影 | DONE (2747 passed/2 skipped) |
| R3a 撤 SDK 旧导出 + 决策 7 最终闸 | DONE (commit 62070cee，2747 passed/2 skipped) |
| R3b products/ 物理解散（-4986 行） | DONE (commit 755e696c，2576 passed/2 skipped) |
| R4 live 实测 R-CFG-1/2/3/4 + R-GW-1/2 | DONE（全 6 项 live PASS）|

### Spec 覆盖

delta-spec 全部 requirement 在代码库中均有实现，见 §Correctness 详表。

---

## Correctness

### §7.0 软对账：delta-spec requirements/scenarios 映射

| Requirement | Scenario | 实现位置 | 测试 | 状态 |
|---|---|---|---|---|
| 精确表面守卫 | 新增导出未进允许名单 → guard 失败 | `tests/contract/test_agent_sdk_surface_guard.py:71` | `test_sdk_all_equals_expected_surface` | covered |
| 精确表面守卫 | 导出对象由内核内部模块拥有 → guard 失败 | `test_agent_sdk_surface_guard.py:118` | `test_sdk_exports_are_sdk_owned_or_explicitly_exempt` | covered |
| 精确表面守卫 | 豁免名单（RunOrigin/PermissionDecision/TERMINAL_RUN_STATUSES） | `test_agent_sdk_surface_guard.py:91-107` | `test_exemption_names_are_actually_exported` | covered |
| 精确表面守卫 | sdk-owned typing 别名（CanUseToolFn）不计入豁免 | `sdk/__init__.py:61`，guard 特判 | `test_sdk_exports_are_sdk_owned_or_explicitly_exempt` | covered |
| 装配与会话分两层 | 应用零前置调用直接装配 | `sdk/kernel.py:77-136`（`build_kernel` 内部 init_model_registry） | `test_llm_config_from_env_needs_no_registry` (contract/test_sdk_two_layer_assembly.py:105) | covered |
| 装配与会话分两层 | 三类应用对内核同构 | `sdk/kernel.py:77`，无 product 分支 | `test_sdk_kernel_wiring.py`（外部产品最小证明） | covered |
| 装配与会话分两层 | 工具目录共享、会话选子集 | `kernel.py:609-636`（`enabled_tools → tool_allowlist`） | `test_sdk_kernel_wiring.py` | covered |
| LLM 配置经单一 LLMConfig | 零前置直接装配 | `sdk/kernel.py:139-192`（`_init_model_registry_from_llm_config`） | `test_llm_config_from_env_needs_no_registry` | covered |
| LLM 配置经单一 LLMConfig | get_llm_config/reconfigure_llm 返回 SDK-owned DTO | `kernel.py:1015-1039` | `tests/contract/test_kernel_sdk_behavior_contract.py` | covered |
| 原生 Tool/Hook 对象扩展 | 对象满足 Tool 契约即可装配 | `sdk/contracts.py:44-78`（@runtime_checkable Protocol） | `test_native_object_satisfies_tool_protocol` | covered |
| 原生 Tool/Hook 对象扩展 | 副作用工具闭包直连、无内核回桥 | `personal_assistant/tools/cron.py:495`（`make_cron_tool(cron_services)` 闭包直连 CronExecutionService，HostCapabilityDispatcher 已删） | `test_cron_tool_closure` | covered |
| 工具展示由 presenter 决定 | 自带 presenter 的工具产出自定义展示 | `platform/tools/builtins/read.py`（`presenter = _READ_PRESENTER`）+ `platform/hooks/builtins/realtime_stream.py:10-29` | `test_sdk_kernel_wiring.py`（live hook chain 含 presenter） | covered |
| 工具展示由 presenter 决定 | 无 presenter 的工具走默认展示 | `platform/tools/presentation.py:42-43`（`presenter or _DEFAULT`） | `test_sdk_kernel_wiring.py` | covered |
| feature 内核只留通用项 | 通用 feature 由会话开关 + 工具在场门控 | `kernel.py:615-620`（features → agent_features metadata），runtime 侧 `resolve_flags_from_metadata` | `tests/integration/test_prompt_sections_golden.py`（pa_heartbeat_on/cron_on golden） | covered |
| feature 内核只留通用项 | 产品条件 prompt 经 PromptSlots 在 create_session 注入 | `personal_assistant/product.py:284-345`（`prompt_for` 拼 PromptSlots） | `test_cron_prompt_sections.py`、`test_heartbeat_prompt_openclaw.py`、`test_communication_context.py` | covered |
| feature 内核只留通用项 | 能力查询返回内核 feature、产品对外 feature 由应用投影 | `sdk/kernel.py:945-974`（`list_features` 只报 memory_curation/skill_creation）；Gateway `capability_projection.py` 投影 heartbeat/cron | `test_capability_payload_baseline.py` | covered |
| PromptSlots 系统提示 | 产品内容在会话内稳定 | `kernel.py:633`（`register_session_prompt_slots` 建会话时一次注册）；不提供 per-turn 注入通道 | `test_full_system_prompt_byte_identical` (integration) | covered |
| PromptSlots 系统提示 | 相同条件下 prompt 逐字节等价 | `tests/integration/golden_prompts/*.txt`（M1 R1 冻结快照）+ `test_kernel_skeleton_reproduces_golden` | 14 golden 全绿 | covered |
| PromptSlots 系统提示 | prompt preview 与真实装配同源 | `kernel.py:1179-1291`（`assemble_prompt_preview(prompt=PromptSlots,...)`；与 `create_session` 共同 `prompt_for` 工厂） | `test_capability_payload_baseline.py` R-CFG-4 live PASS | covered |
| Kernel 单项中立能力查询 | 能力查询与运行时事实一致 | `sdk/kernel.py:872-1013`（`list_models/tools/features/skills`） | `test_kernel_list_capability_queries` (4 passed) | covered |
| Kernel 单项中立能力查询 | 跨 workspace 的 skill 查询互不混用 | `kernel.py:976-1013`（per-call `_WorkspaceDirnameSkillResolver`，不复用 build-time resolver） | R-CFG-2 live PASS | covered |
| Kernel 单项中立能力查询 | 部署级共享 skill 根叠加在每 workspace 根之上 | `sdk/kernel.py:476-508`（`_WorkspaceDirnameSkillResolver.extra_roots`，workspace 优先 → extra_roots 去重保序） | `test_capability_payload_baseline.py`（skills 4 类 payload 逐字段绿） | covered |
| Kernel 出入参为 SDK-owned 类型 | 会话与运行结果不暴露内核内部对象 | `kernel.py:212-233`（`_to_session_info`/`_to_run_info` boundary mapping）；`sdk/dto.py:22-59` | `test_session_info_fields_and_frozen`、`test_run_info_fields` | covered |
| 会话档案为无状态 per-workspace JSONL | 不同 agent 会话落各自 workspace | `kernel.py:609`（`effective_root = workspace_root or self._repo_root`），`JsonlSessionStore` 无状态 | R-GW-3 live PASS（JSONL per-workspace） | covered |

**§7.0 软对账结论：**
- 契约与实现一致：全部 24 条 Requirement/Scenario
- 契约声明的行为代码已背离：无
- 本 unit 新增代码产生 delta 未覆盖的对外行为：`assemble_prompt_preview` 新增 `prompt=PromptSlots`/`enabled_tools` 入参（legacy `tool_ids`/`custom_prompt` 保留兼容），此行为扩展在 design 决策 8 中明确（"入参对齐 create_session：`prompt=PromptSlots`/`features`/`enabled_tools`/`workspace_root`/`scenario`"），有 delta-spec Scenario「prompt preview 与真实装配同源」覆盖。

---

## Coherence

### design 决策 1-12 遵守情况

| 决策 | 描述 | 遵守 | 代码证据 |
|---|---|---|---|
| 决策 1 | 取消产品层，2 层装配 + 消费者工厂 | ✅ | `sdk/kernel.py:77`（`build_kernel` 无 product_profile）；`agent/products/` 已删除；`coding_cli/product.py`、`personal_assistant/product.py` 各自工厂 |
| 决策 2 | 原生 Tool/Hook 对象，SDK-owned Protocol | ✅ | `sdk/contracts.py`（Tool/ToolContext/HookAPI 三 Protocol）；`build_kernel(tools=[], hooks=[])` 直接装配 |
| 决策 3 | feature 内核只留通用两条，产品专属走 PromptSlots | ✅ | `kernel.py:965`（list_features 过滤只报 memory_curation/skill_creation）；heartbeat/cron/群聊全在 `personal_assistant/product.py:prompt_for` |
| 决策 4 | Kernel 单项中立查询，Gateway 投影 | ✅ | `kernel.py:872-1013`（list_*）；`personal_assistant/reporter/capability_projection.py`（Gateway 投影层）；reporter 不再 import SDK 旧导出 |
| 决策 5 | LLM 经 LLMConfig，model 维持 kernel 级 | ✅ | `sdk/dto.py:95`（LLMConfig）；`kernel.py:139`（内部 init）；`create_session` 不收 model |
| 决策 6 | Kernel 出入参 SDK-owned 冻结 DTO | ✅ | `sdk/dto.py:22`（SessionInfo/RunInfo）；`kernel.py:212-233`（边界映射函数）；`agent.sdk.__all__` 精确名单守卫 |
| 决策 7 | 精确名单 + 所有权 + 豁免名单 contract 测试 | ✅ | `tests/contract/test_agent_sdk_surface_guard.py`（3 道闸，EXPECTED_SURFACE=22 符号，M2 最终闸已去除 _M1_TEMP）；6 passed |
| 决策 8 | 内核模板骨架 + PromptSlots 四槽，纯 per-session | ✅ | `sdk/prompt.py`（PromptSlots/PromptText）；`kernel.py:633`（register_session_prompt_slots）；golden 14 绿 |
| 决策 9 | PA 工具迁出内核，cron 闭包直连，HostCapabilityDispatcher 删除 | ✅ | `personal_assistant/tools/cron.py:495`（make_cron_tool 闭包）；全仓无 host_capability.py；无 HostCapabilityDispatcher 符号 |
| 决策 10 | JsonlSessionStore 无状态，位置由 workspace_root | ✅ | `kernel.py:609`（per-session effective_root）；JSONL 位置由 workspace_config_dirname 约定派生 |
| 决策 11 | 三段式共存迁移，2 milestone 垂直切 | ✅ | M1 R1-R7 + M2 R1-R4 全部 DONE |
| 决策 12 | presenter 随 Tool 对象走，删全局注册表 | ✅ | `platform/tools/builtins/read.py`（`presenter = _READ_PRESENTER` 类属性）；`platform/tools/presentation.py:28-43`（`resolve_presenter_for_tool` 走 getattr(tool,"presenter",None)）；无 `_PRESENTERS` 全局 dict |

### 架构自洽性（§4.3）

- **依赖方向**：`coding_cli` / `personal_assistant` 只 import `agent.sdk`——`test_agent_sdk_boundary_contract` 6 passed 自动守卫；全仓无 `from agent.core` / `from agent.platform` 在产品包中出现。
- **跨机/进程边界**：cron 闭包持有 `CronExecutionService` 句柄（同进程），无跨进程假设；reporter 调 `kernel.list_*`（同进程），无跨机边界问题。
- **复用 vs 平行**：capability 查询通过 `kernel.list_*` 扩展了既有 Kernel 接口，未造平行机制；presenter 附工具对象取代全局 registry，无平行注册表。

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

**W1：canonical kernel spec（`docs/specs/kernel/spec.md`）尚未归并 delta-spec，仍记录旧 API**

- **问题**：`docs/specs/kernel/spec.md:46` 中 `build_kernel` 签名仍为旧格式 `build_kernel(product_profile, llm_config, can_use_tool, repo_root, host_capabilities=...)`，引用了 `ProductProfile`、`LLMFactoryConfig`、`HostCapabilityDispatcher` 等已被本 unit 彻底删除的符号。契约层与实现不一致。
- **影响**：下游开发者读 `docs/specs/kernel/spec.md` 会拿到错误的 API 规格；长青契约失去「current 权威」地位。
- **修复建议**：将 `docs/changes/refactor-406-sdk-curated-surface/specs/kernel/spec.md`（delta-spec）归并进 `docs/specs/kernel/spec.md`：
  1. 替换 `§Requirement: build_kernel 装配出可用的进程内 Kernel`（line 43-75）为 delta-spec 的「装配与会话分两层，内核产品中立」Requirement + Scenarios。
  2. 删除引用 `ProductProfile`/`LLMFactoryConfig`/`host_capabilities`/`HostCapabilityDispatcher` 的所有 Scenario（line 46, 54-70）。
  3. 追加 delta-spec 的全部 ADDED Requirements（Tool/Hook 协议、PromptSlots、list_* 查询、SDK-owned DTO、presenter、会话档案）。
  4. 按 `docs/SPEC_GUIDE.md` 的归并纪律（「收尾归并」节）操作；同步更新 `test_multi_product_architecture.py:KERNEL_REQUIRED_DOC_SNIPPETS`（当前 snippet 若涉旧措辞需同步）。
- **注**：M2 progress.md 已记为「非阻塞，待 orchestrator 裁」。orchestrator 可派 worker 在独立 roadpoint 执行此归并（约 1-2h 工作量）。

### SUGGESTION（可以修）

**S1：M2 无独立 tasks.md，进度全在 progress.md**

- **观察**：M2 milestone 目录只有 `progress.md`，无 `tasks.md`（M1 有）。progress.md 记录了所有 roadpoints 和退出证据，功能完整，但与 M1 格式不一致。
- **建议**：若后续 verifier/orchestrator 期望每个 milestone 都有 tasks.md，可补一份简要 tasks.md（仅列 roadpoints 和 `[x]` 状态）；否则 progress.md 已足够，可保持现状。非 PR 阻塞。

---

No critical issues. 1 warning to consider. Ready for PR (with noted improvements).
