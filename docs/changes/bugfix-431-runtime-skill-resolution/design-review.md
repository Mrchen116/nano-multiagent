# Design 评审: bugfix-431-runtime-skill-resolution

**结论**: Issues Found

**评审日期**: 2026-06-24

## 核实台账

逐条核过的承重原子；结论附证据，不是打勾。

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状: `build_kernel()` 未传 config_resolver/workspace_config_dirname/skill_search_roots 给 AgentRuntime | 从 `build_kernel` → `_build_kernel_base` 追 wiring | ✅ 成立。`kernel.py:389-400` 构造 AgentRuntime 无上述参数；`workspace_config_dirname`/`skill_search_roots` 仅存 Kernel 实例(`kernel.py:520-528`) |
| 现状: `Kernel.list_skills` 内联构造 `_WorkspaceDirnameSkillResolver` | 读 `kernel.py:1163-1167` | ✅ 成立。`per_call_resolver = _WorkspaceDirnameSkillResolver(workspace_root=..., workspace_config_dirname=..., extra_roots=...)` |
| 现状: `Kernel.assemble_prompt_preview` 同样内联构造 | 读 `kernel.py:1427-1435` | ✅ 成立。`preview_resolver = _WorkspaceDirnameSkillResolver(...)` |
| 现状: `AgentRuntime.config_resolver` 恒为 None | 追 wiring | ✅ 成立。`runtime.py:117` 默认 None；`build_kernel` 从未传值(`kernel.py:389-400`) |
| 现状: `_resolve_session_available_skills*` 传 `self._config_resolver` (None) | 读 `runtime.py:1307,1323` | ✅ 成立。两处均 `config_resolver=self._config_resolver` |
| 现状: `config_resolver=None` 时回退 Codex 默认 roots | 读 `discovery.py:38-49` | ✅ 成立。roots = `~/.codex/skills` + `<ws>/.codex/skills` + `<ws>/.nano/skills` |
| 现状: `config_resolver` 非 None 时忽略 workspace_root | 读 `discovery.py:27-36` | ✅ 成立。直接 `return config_resolver.user_skill_roots()` |
| 现状: agent 工具 `getattr(runtime, "config_resolver", None)` | 读 `agent.py:660` | ✅ 成立。`resolve_available_skills(workspace_root=ctx.repo_root, ..., config_resolver=getattr(...))` |
| 现状: `_WorkspaceDirnameSkillResolver` 构造被 list_skills 和 preview 两处独立内联(无统一 helper) | grep `_make_skill_resolver` | ✅ 成立。`_make_skill_resolver` 在当前代码库不存在，两处各写一遍 |
| 现状: `config_resolver` 引用点全仓共 6 处在 runtime.py | grep 全仓 | ✅ 成立。runtime.py 内 6 处(定义+存储+property+两处调用)；agent.py 1 处(getattr)；loader.py/hooks_loader.py 不读 runtime 的 property |
| 现状: `ConfigResolverLike` Protocol 仅被 runtime.py 使用 | grep | ✅ 成立。`runtime.py:94` 定义，`runtime.py:117,962` 使用。tool/hook loader 有各自独立的 `_ToolRootResolver`/`_HookRootResolver` |
| 既有约束: coding_cli/PA 只能 import agent.sdk | 核 spec | ✅ 成立。kernel spec Requirement 1 + `test_agent_sdk_boundary_contract.py` |
| 既有约束: refactor-406 退役 ConfigResolver | incident + design 均引用 | ✅ 成立。design 决策 1/3 拒绝复活 |
| 决策 1: AgentRuntime 持有 dirname+roots，按需构造 resolver | 四问 | ✅ 拍死、自洽。拒绝固定 resolver(per-agent 隔离)、拒绝复活 ConfigResolver、不改 resolve_available_skills 签名 |
| 决策 2: 抽取 `_make_skill_resolver` 统一 helper | 四问 + 对比其他组件模式 | ✅ 拍死、自洽。位于 sdk 层(需 `_WorkspaceDirnameSkillResolver`)、不放 core 层(破坏依赖方向)。features/prompt_context 已采用同源 helper 模式且运行良好，本决策将 skills 对齐到同一模式 |
| 决策 3: 移除 config_resolver property，新增 resolve_available_skills 方法 | 四问 + 数据流 | ✅ 拍死。config_resolver 引用点仅 agent.py 一处需改；但**风险缓解描述与事实不符**（见 Issue 1） |
| 决策 4: 清理 Codex roots 默认回退 | 四问 | ✅ 拍死、有 spec 驱动(delta-spec 场景 3)。需同步更新所有 `config_resolver=None` 调用点 |
| spec 约束 Q2: runtime 与 preview 同源 | incident 澄清记录 | ✅ 决策 2 直接覆盖 |
| spec 约束 Q3: 不存在的 skill 静默忽略 | incident 澄清记录 | ✅ `_WorkspaceDirnameSkillResolver` 已有此行为，统一后自然继承 |
| delta-spec kernel: ADDED Requirement | 用法检查 | ✅ 新增行为保证(原 spec 无此 requirement)，非改既有，ADDED 正确 |
| delta-spec 场景 1: preview 与 runtime 一致 | THEN 可观察？ | ✅ 「`SkillMetadata` 集合相同」是消费者可观察，无内部符号 |
| delta-spec 场景 2: 子 agent 加载技能同源 | THEN 可观察？ | ✅ 「覆盖 workspace_config_dirname 下的 skills 目录与 skill_search_roots」是可观测行为 |
| delta-spec 场景 3: 未提供 dirname 时无隐式默认 roots | THEN 可观察？ | ✅ 「返回空 skills 列表」是可观测行为 |
| M1: 单 milestone，垂直切片 | 垂直 vs 横切 | ✅ 单 M1 覆盖 sdk→core→platform 全链路 + 测试 + 验收，端到端可观测 |
| M1 退出标准 | 两轨齐？ | ✅ `[reviewer]` 轨有用户可观察(12 skills 出现在 LLM 请求、子 agent 加载成功)；`[worker]` 轨有测试+构建 |
| M1 范围文件 | 跨包是否合理？ | ✅ 改动落 sdk/core/platform 三包各一处，范围无交集、逻辑不可再切 |
| Runbook | 可直接照搬？ | ✅ IM + Gateway 启停命令完整，健康检查明确 |
| 接口数据流 | 闭合？ | ✅ PA→build_kernel→AgentRuntime→helper→resolve_available_skills→LLM，每步有出口 |
| 其他组件模式对比 | 探索 features/tools/hooks/prompt_context 的 preview/runtime 同源策略 | ✅ features 和 prompt_context 已走统一 helper 模式；tools/hooks 机制本就不同且不存在漂移风险；design 的 `_make_skill_resolver` 将 skills 对齐到既有最佳实践 |

## Issues

### [WARNING] 风险缓解 1 的 contract test 声明与事实不符

**位置**: 风险与回退 > 已知风险 1

**问题**: design 声称「`tests/contract/test_agent_sdk_surface_contract.py` 会自然拦住下划线符号进入 `EXPECTED_SURFACE`」——但实际该测试**不检查私有符号泄漏**，只验证 public allowlist 和 cron 隔离。`_make_skill_resolver` 泄漏到 `agent.sdk` 公开面时不会被自动拦截。

**不改→下游出什么坏事**: worker 可能认为有自动守卫而放松手动检查，helper 意外导出无人发现。

**建议**: 在 M1 worker 退出标准中显式加一条「`dir(agent.sdk)` 不含 `_make_skill_resolver`」的断言，或在 `test_agent_sdk_surface_contract.py` 补一条负向测试。

### [WARNING] 调用方改造清单遗漏 `test_core_skills_location.py`

**位置**: 关键决策 > 决策 4 + 接口与数据流 > 调用方改造清单

**问题**: `default_skill_search_roots` 当前是 `agent.core.skills.__all__` 的公开导出，且 `tests/unit/test_core_skills_location.py` 显式 import 并断言其存在性和模块归属（`test_core_skills_location.py:29-35`）。决策 4 改其 `config_resolver=None` 分支返回空元组，会让依赖旧行为的测试失败。

**不改→下游出什么坏事**: worker 改了函数行为却漏更新断言，CI 红。

**建议**: 调用方改造清单补充 `tests/unit/test_core_skills_location.py`，明确该测试需同步更新。

### [WARNING] 决策 3 的 tools/hooks 不对称未说明

**位置**: 关键决策 > 决策 3

**问题**: design 移除 `AgentRuntime.config_resolver` property，但 `platform/tools/loader.py` 和 `platform/hooks/loader.py` 仍有各自的 `config_resolver` 参数(接受 `_ToolRootResolver` / `_HookRootResolver` Protocol)。当前 SDK wiring 已独立构造 tool/hook resolver、不走 runtime property，所以移除安全；但留下「skills 走 runtime 方法、tools/hooks 走独立 resolver 注入」的不对称。

**不改→下游出什么坏事**: 本次无害，但后续维护者可能困惑为什么三类插件发现走了不同路径；worker 可能误以为遗漏而做多余改动。

**建议**: 在 design 现状分析或决策 3 的「拒绝」段加一句说明此不对称是刻意的（tools/hooks 的 resolver 由 SDK 装配层直接注入，不经过 runtime），避免 worker 误判。

## Recommendations

不阻断门禁，作者自行取舍。

1. **决策 2 理由段补一句模式对齐说明**: features / prompt_context 已采用同源 helper 模式且运行良好，本决策将 skills 对齐到同一模式。让 reviewer 一眼看出这不是新发明而是既有最佳实践的延续。
2. **决策 3 「拒绝」段补 tools/hooks 不对称说明**: tools/hooks 的 resolver 由 SDK 装配层直接注入（build-time），不经过 runtime property，因此移除 config_resolver 不影响它们。
3. **delta-spec 场景 3 GIVEN 简化**: 当前写「未传入 `workspace_config_dirname` 也未显式提供 resolver」——后半句「未显式提供 resolver」在新架构下语义模糊（`config_resolver` 已被移除），建议简化为「未传入 `workspace_config_dirname`」。
4. **风险段补 `ConfigResolverLike` Protocol 清理说明**: 移除 `config_resolver` property 后，`ConfigResolverLike` Protocol（`runtime.py:94`）仅剩定义行无引用方，可一并移除。但需注意 tool/hook loader 各有独立 Protocol（`_ToolRootResolver` / `_HookRootResolver`），不受影响。
