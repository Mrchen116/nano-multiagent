# refactor-406-M1 — Progress

## 启动对齐（§2.5）

- 已读：motivation.md / design.md（决策 1/2/3/5/6/8/9）/ kernel delta-spec / kernel.py / bootstrap.py / products/base.py / PA profile+prompt_sections / core_sections.py / base.py（prompt 装配）/ feature_registry.py / wiring.py / host_capability.py / cron.py / surface contract / TESTING_GUIDE + 消费者调用点。
- 基线：`pytest -m "not e2e"` 2697 passed / 2 skipped 全绿。
- orchestrator 答复（team-lead）：
  - Q1：M1 所有权闸真立起来并绿；暂留 reporter 旧导出（SkillRegistry/ConfigResolver/default_skill_search_roots/FEATURE_REGISTRY/model registry 列表函数）走豁免名单临时扩容，显式标注 `_M1_TEMP_REPORTER_EXPORTS`，与 C1 永久豁免（RunOrigin/PermissionDecision/TERMINAL_RUN_STATUSES）物理分开；M2 删旧导出时同步从豁免名单移除。
  - Q2：products/ 解散把所有 PA 专属资产（profile/prompt_sections/tools/hooks/skills 物理目录）下沉 src/personal_assistant/，`_product_root()` 扫描退役，属 M1（只排除 reporter/，归 M2）。
  - golden-first 顺序（先补 cron verbatim + 录重构前完整 prompt 快照，再动装配）获认可。

## R1 — cron 段逐字节 golden + 完整 prompt 重构前基线快照

- Context: design 风险 1（prompt 字节漂移）是 M1 最高风险——cron/heartbeat/群聊三段要从内核 segment 迁到 PA PromptSlots，模板装配改造。skill 与 orchestrator 都要求 golden 防线先就位再迁。现状 `test_cron_prompt_sections` 对 cron 段仅 `len>20` 弱断言，无逐字节防线；仓内无「完整 system prompt 逐字节」golden（既有 golden 测试都是内容 presence 断言）。
- Decision:
  1. 新建 `tests/integration/test_full_system_prompt_byte_identical.py` + `tests/integration/golden_prompts/*.txt`：场景矩阵（PA direct/cron/heartbeat/both/group/custom + LC full）的**完整 assembled prompt** 逐字节快照。golden 在重构前代码录制锁定。`_assemble_full_prompt(product, ctx)` 是装配 seam——R1 走旧路径（build_<product>_system_prompt + assemble_system_prompt），后续 roadpoint 把其内部改走内核模板骨架 + PromptSlots，golden 字节冻结。
  2. 升级 `test_cron_prompt_sections`：`test_pa_cron_segment_renders_content`（len>20）→ `test_pa_cron_segment_renders_verbatim` + 新增 `test_pa_cron_routing_segment_renders_verbatim`，两段 cron 文案逐字节钉死。
- Rationale: 完整 prompt 逐字节 golden 是「重构前=重构后」的可执行守卫（红了即停），覆盖 design 退出标准「PA 群聊/heartbeat/cron 各配置 + CLI 完整 system prompt 逐字节」。seam 设计让装配路径可在后续 roadpoint 替换而 golden 不动，正是逐字节等价的钉死方式。golden 文件有长期回归价值（整个重构期 + 未来 prompt 改动都该跑），属永久回归测试不是一次性证据。
- Evidence:
  - Tests: `pytest tests/unit/personal_assistant/test_cron_prompt_sections.py tests/integration/test_full_system_prompt_byte_identical.py` → 14 passed（重构前代码上全绿，基线锁定）。golden 文件 7 个：pa_direct_basic(7970) / pa_cron_on(8598) / pa_heartbeat_on(8186) / pa_both_on(9304) / pa_group(8576) / pa_custom(8020) / lc_full(6431) bytes。
  - Entry: N/A（R1 是 golden 基线锁定，无运行时入口；运行时 prompt 装配在 R6 走 live PA + 预览同源验证）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: golden 测试即 regression 防线，路径见上；后续每个 roadpoint 都跑它确认零漂移
  - Visual/Interaction: N/A
- Rollback: 单 commit，`git revert` 即移除 golden 测试 + 文件 + cron verbatim 升级，回到 R1 前
- Commits: C1=85a5d63c (R1 是 Verify-only 基线锁定，单 commit)

## R2 — 内核模板骨架 + PromptSlots 四槽（扩张，旧路径不动）

- Context: 决策 8 核心——内核拥有产品中立固定顺序模板骨架，产品文案经 PromptSlots 四槽 per-session 注入，逐字节复现现状。这是 prompt 重构的地基；扩张段（旧 build_<product>_system_prompt 路径不动）。
- Decision:
  1. `src/agent/sdk/prompt.py`：`PromptSlots(head/body/custom/tail)` + `PromptText(name,text)` SDK-owned 冻结值对象，每槽一组 PromptText。
  2. `src/agent/core/agent/prompt_sections/skeleton.py`：`build_kernel_prompt_skeleton()` 返回固定顺序 section 列表——slot section（head/body/custom 稳定、tail 易变 cache_safe=False）与 core 段交织：`head → CORE_SYSTEM/ACTIONS/TOOL_RULES/TONE → body → CORE_SKILLS_LISTING/MEMORY_GUIDANCE/SKILLS_GUIDANCE → CORE_BACKGROUND_TASKS/RUNTIME_FOOTER → custom → CORE_MEMORY_BLOCK/USER_PROFILE_BLOCK → tail`。slot section 鸭子读 `ctx.prompt_slots.<slot>`（不 import sdk）。
  3. `PromptContext` 加 `prompt_slots: object | None`（鸭子结构，core 不 import sdk）。
- Rationale: 顺序按**字节真相**搭（见下 Design 修订 §R2）——feature 指引在 body 后、custom 在 footer 后易变尾前——而非 design §251 prose 那个顺序，否则破坏 golden。slot 用 PromptText 序列（非单串）是为复现现状多段 `\n\n` 布局（如 identity+runtime 两段）。复用既有 `assemble_system_prompt`（cache_safe 校验 + `\n\n` join），字节一致结构性保证。SDK-owned + core 鸭子读 = 满足决策 7 所有权闸且无 core→sdk 倒挂（同决策 2 Protocol 思路）。
- Evidence:
  - Tests: 新 `tests/integration/test_kernel_skeleton_reproduces_golden.py` 7 场景全绿（skeleton+slots 逐字节重现 R1 golden）；R1 golden 7 绿；prompt 相关全套（tests/unit/agent + integration prompt + unit/personal_assistant）1090 passed/1 skipped；contract 112 passed。零回归。
  - Entry: N/A（扩张段无运行时入口；运行时装配 R6 走 live + 预览同源）
  - Frontend State Matrix / Browser QA / Visual: N/A
  - E2E/Regression: golden + skeleton-重现-golden 两道防线，后续 roadpoint 持续跑
- Rollback: C2 revert 移除 skeleton/slots（旧路径仍在，零影响）；C1 revert 移除红测
- Commits: C1=e64b5a96, C2=e7133b5c, C3=4e4ee4e5

## [Design 修订] R2: 决策 8 §251 骨架顺序 prose 与字节真相不符

- 现状方案: design §251 写骨架顺序 = `head → core 行为规则 → 通用 feature 指引(memory/skill) → body → 后台/footer → 易变尾部 → tail`（feature 指引在 body **之前**，未显式给 custom 定位）。
- 新方案: 按 PA/LC 现状逐字节真相搭骨架 = `head → core 规则 → body → 通用 feature 指引 → 后台/footer → custom → 易变尾部 → tail`（feature 指引在 body **之后**，custom 在 footer 后、易变尾前）。
- 原因: byte-identical（risk 1 / kernel delta-spec「逐字节等价」Scenario）是硬契约；§251 顺序 prose 是示意，与 golden 锁定的实际装配顺序冲突，照 prose 搭会破坏 golden。
- 影响范围: 仅文档表述（§251 prose）；不影响行为/退出标准。M2 reporter 不依赖此顺序。
- design.md 是否同步改: 待 orchestrator 定（已 SendMessage 报备，问①同意按字节真相②是否顺手改 §251 prose）。代码已按字节真相落地并 golden 守绿，design 文本修订不阻塞实施。

## R3 — build_kernel 基座 + create_session per-agent + DTO + Protocol（扩张）  [部分完成 / HANDOFF]

- Context: M1 最大代码块。三段式扩张：新表面长出、旧导出/旧签名不动、测试零改动保持绿。
- 已完成（committed + pushed）：SDK building blocks（纯增量，未接入 kernel，零回归）
  - `src/agent/sdk/dto.py`（C1=d3b6b29d 红测 / C2=7b90ae84 实现）：`SessionInfo`/`RunInfo`（决策6 边界 DTO）+ `LLMConfig`（决策5，`from_env` 纯 env、去掉「先 init_model_registry」footgun）+ `LLMProvider`/`LLMModel` catalog + `ModelInfo`/`ToolInfo`/`FeatureInfo`/`SkillInfo`（决策4 能力查询 DTO）。
  - `src/agent/sdk/contracts.py`（同 C2）：`Tool`/`ToolContext`/`HookAPI` runtime_checkable 结构 Protocol（决策2）。已验证 core 真对象（`core.tools.base.ToolContext` 加 safety、`core.hooks.registry.HookAPI`）鸭子满足，无 core→sdk 倒挂。
  - 测试 `tests/contract/test_sdk_two_layer_assembly.py` 10 passed；全量基线 `pytest -m "not e2e"` 2722 passed / 2 skipped 零回归；ruff check + format 干净。
- **未完成（HANDOFF 续做）**：把上述 building blocks **接入 kernel.py**——仍需：
  1. `build_kernel` 改双签名（扩张期）：保留旧 `product_profile=` 路径不动，新增 `llm=LLMConfig, tools=[Tool对象目录], hooks=[setup callable], can_use_tool, workspace_config_dirname, repo_root`。新路径不走 `bootstrap_product(profile=)`，而是从 LLMConfig 内部 init 模型注册表（`init_model_registry`，消化 footgun）+ 用传入 tools 对象目录建 ToolRegistry（参考 `platform/tools/loader.build_tool_registry` 的对象注册）+ hooks setup 注册（参考 `platform/hooks/loader`）+ 共享 store 组件（`JsonlSessionStore(data_dir=None, workspace_config_dirname=...)`）。共享资源建一次。
  2. `create_session` 新增 per-agent 入参：`enabled_tools`（从基座目录选子集，参考 bootstrap `_filter_tool_registry`）/`features`（内核两条开关→flags）/`prompt=PromptSlots`（注入 `PromptContext.prompt_slots`，走 R2 `build_kernel_prompt_skeleton`）；返回 `SessionInfo`（边界 map，保 `.session_id` 属性访问）。旧 `skills`/`tool_allowlist` 入参扩张期暂留。
  3. 出入参 DTO 化：`submit`/`get_run`/`cancel`→`RunInfo`；`get_llm_config`/`reconfigure_llm`→`LLMConfig` DTO（保 CLI `/model` 即时生效）；`fork_session`→`SessionInfo`。
  4. `list_models`（LLMConfig catalog + 默认）/`list_tools`（基座目录 name/description）/`list_features`（FEATURE_REGISTRY 内核两条 memory_curation/skill_creation 投影成 FeatureInfo）/`list_skills(workspace_root)`（`resolve_available_skills`）。
  5. 运行时 prompt 装配切到骨架 + slots：`runtime._run_locked`（约 line 403-438）现走 `self._prompt_sections`（旧 build_<product>_system_prompt 列表）+ `resolve_effective_prompt`；新路径要让 runtime 用 `build_kernel_prompt_skeleton()` + ctx.prompt_slots（slots 由 create_session 存进 session metadata 或 runtime 配置，per-session 稳定）。**改这里务必跑 R1/R2 golden 守字节**。
  6. C1 测试：扩展 `test_sdk_two_layer_assembly.py` 或新增——build_kernel 新签名装配可用、enabled_tools 子集、features 门控、list_* 与运行时一致 + 跨 workspace skill、外部产品最小证明（agent 包外应用仅经 agent.sdk 装配 + create_session + 工具调用一轮，含闭包直连自己服务的副作用工具）。
  7. `agent.sdk.__init__` 把 build_kernel/Kernel/PromptSlots/PromptText/Tool/ToolContext/HookAPI/SessionInfo/RunInfo/LLMConfig + list_* 相关 DTO 加进 `__all__`（精确名单 R7 落闸时统一钉死）。
- Evidence:
  - Tests: building-block 10 passed；全量基线 2722 passed/2 skipped 零回归；ruff 干净。
  - Entry: 待 R5/R6 live（CLI 工具调用 / PA 发消息 / 预览同源）
  - Frontend State Matrix / Browser QA / Visual: N/A
  - E2E/Regression: R1 golden + R2 skeleton-重现-golden 持续守；接入 runtime 后必跑
- Rollback: building blocks 是纯增量，revert C1/C2 即移除，不影响任何现有路径
- Commits: C1=d3b6b29d, C2=7b90ae84（building blocks）；kernel 接线未提交

## HANDOFF 状态（给续做 worker / orchestrator）

- 已完成并 push：R1（golden 防线）、R2（内核骨架+PromptSlots）、R3 building blocks（DTO/Protocol）。全绿、零回归。
- 续做入口：本文 R3「未完成」7 步，从第 1 步 build_kernel 双签名起。**最关键守卫**：改 runtime prompt 装配（第 5 步）后必跑 `tests/integration/test_full_system_prompt_byte_identical.py` + `test_kernel_skeleton_reproduces_golden.py`，红即停（risk 1）。
- 之后 R4（cron 迁出内核 + HostCapabilityDispatcher 删除，cron 闭包直连 CronExecutionService，PA tools/hooks/skills 物理目录搬 src/personal_assistant/）、R5（coding_cli 切新表面 + live：R-CLI-1/2/3）、R6（personal_assistant 工厂 prompt_for + main 装配 + 预览同源 + live：R-PA-1/2/3、R-CP-1/2/3、R-GW-3）、R7（products 解散 + bootstrap _product_root 退役 + 旧导出清零 + 决策7 三道闸：精确名单 EXPECTED_SURFACE + 所有权闸 + 豁免名单含 `_M1_TEMP_REPORTER_EXPORTS`）。
- live-critical（cron/heartbeat/群聊运行时 + prompt 运行时装配）需真端到端证据（§0.3/§0.11），env 起不来按 §0.11 找 orchestrator，不自降证据。
- 待 orchestrator 答复：design §251 骨架顺序 prose 是否修订（不阻塞代码）。
