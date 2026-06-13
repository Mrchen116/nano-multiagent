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
- design.md 是否同步改: **不改**（orchestrator 裁定：design.md 是 design-author 所有权域，§0.3 硬规则，orchestrator/worker 都不动正文；§251 prose 修正由 orchestrator 作为非阻塞 doc nit 上报用户、design-author 后续收口）。
- **权威骨架顺序（字节真相，以此为准，覆盖 design §251 prose）**：
  `head → core 规则(system/actions_care/tool_rules/tone_style) → body → 通用 feature 指引(skills_listing/memory_guidance/skills_guidance) → 后台(background_tasks)/runtime_footer → custom → 内核易变尾部(memory_block/user_profile_block) → tail`
  PA 槽映射：head=identity+runtime；body=heartbeat/cron/cron_routing/platform_policy/guidelines/routing；custom=user_custom；tail=communication_context（对齐现状 order 900 易变尾部之后）。
  与 design §251 prose 两处差异：① 通用 feature 指引在 **body 之后**（非 prose 的 body 之前）；② custom 槽在 footer 后、内核易变尾部前（prose 未定位）。reviewer / M2 以本段为权威骨架参照。
- delta-spec 同步: 已把 `docs/changes/refactor-406-sdk-curated-surface/specs/kernel/spec.md` 的「系统提示由内核模板 + PromptSlots 组装」Requirement 骨架顺序句改为字节真相（orchestrator 授权：delta-spec 归本 unit 在 unit 分支维护，非 design 正文）。

## R3 — build_kernel 基座 + create_session per-agent + DTO + Protocol（扩张）  [部分完成 / HANDOFF]

- Context: M1 最大代码块。三段式扩张：新表面长出、旧导出/旧签名不动、测试零改动保持绿。
- 已完成（committed + pushed）：SDK building blocks（纯增量，未接入 kernel，零回归）
  - `src/agent/sdk/dto.py`（C1=d3b6b29d 红测 / C2=7b90ae84 实现）：`SessionInfo`/`RunInfo`（决策6 边界 DTO）+ `LLMConfig`（决策5，`from_env` 纯 env、去掉「先 init_model_registry」footgun）+ `LLMProvider`/`LLMModel` catalog + `ModelInfo`/`ToolInfo`/`FeatureInfo`/`SkillInfo`（决策4 能力查询 DTO）。
  - `src/agent/sdk/contracts.py`（同 C2）：`Tool`/`ToolContext`/`HookAPI` runtime_checkable 结构 Protocol（决策2）。已验证 core 真对象（`core.tools.base.ToolContext` 加 safety、`core.hooks.registry.HookAPI`）鸭子满足，无 core→sdk 倒挂。
  - 测试 `tests/contract/test_sdk_two_layer_assembly.py` 10 passed；全量基线 `pytest -m "not e2e"` 2722 passed / 2 skipped 零回归；ruff check + format 干净。
  - **list_* 已接入并测（C1=a890d489 / C2=3284251d）**：`Kernel.list_models/list_tools/list_features/list_skills` 内核侧产出 SDK-owned DTO（决策4，orchestrator nail ②）。`tests/unit/agent/test_kernel_list_capability_queries.py` 4 passed：list_features 只报内核两条通用 feature（memory_curation/skill_creation，不含 heartbeat/cron 产品 toggle）；list_skills 跨 workspace 不混用。⚠️ **修了一个真 bug**：list_skills 原复用 build 期 config_resolver 会把所有 workspace 解析到 build repo_root 的 skill（`default_skill_search_roots` 在有 resolver 时忽略 per-call workspace_root）；改为按 per-call workspace_root 现造 ConfigResolver（镜像 reporter 模式），跨 workspace 隔离成立（R-CFG-2 相关）。
- **未完成（HANDOFF 续做）**：把剩余 building blocks **接入 kernel.py**——仍需（list_* 第4项已完成，余 1/2/3/5/6/7）：
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

## R3 接线 — build_kernel 双签名 + create_session per-agent + DTO 化（扩张，完成）

- Context: 续跑 worker（m1-worker-2）接 R3 building blocks + list_* 后，完成把 building blocks 真正接入 kernel.py。
  注：接线期发生过一次同 worktree 双 worker 冲突（rebase 重排 + orphan stash），由 orchestrator 协调后本 worker 独占续跑，
  原半成品接线（build_kernel 双签名 ~400 行）经 stash 恢复 + 与已落地 list_* 三方合并，无冲突标记，全测树验证零回归。
- Decision（接线落点）:
  1. `build_kernel` 双签名（扩张期）：`llm=LLMConfig`(新) / `product_profile=`(旧) 二选一守卫；新路径 `_build_kernel_base`
     走 `build_kernel_prompt_skeleton()` 内核骨架 + 内部 `_init_model_registry_from_llm_config`（消化「先 init 再 from_env」
     footgun，catalog 缺省时从 active 连接合成单 provider 目录）+ 原生工具对象 `registry.register(tool, replace=True)`
     （无 `_product_root` 扫描）+ hooks `setup(hook_registry)` 注册 + 共享 `JsonlSessionStore`。
  2. `create_session` 加 `enabled_tools`/`features`/`prompt=PromptSlots`（不收 model，决策5）：`features`→`metadata["agent_features"]`
     门控内核 feature；`enabled_tools`→`tool_allowlist`；`prompt` 经 `runtime.register_session_prompt_slots(session_id, slots)`
     注入 per-session（决策8，**不持久化**——PromptSlots 不能 JSON round-trip，由消费者工厂每进程开会话时重建）；返回 `SessionInfo`。
  3. 出入参 DTO 化（决策6）：`submit`/`get_run`/`cancel`→`RunInfo`(`_to_run_info`)；`fork_session`→`SessionInfo`(`_to_session_info`)；
     `get_llm_config`/`reconfigure_llm`→`LLMConfig` DTO(`_factory_config_to_llm_config`，threading build 期 catalog)。
  4. runtime per-session slots：`runtime.__init__` 加 `_session_prompt_slots` map + `register_session_prompt_slots`；`_run_locked`
     ctx 构造线进 `prompt_slots=self._session_prompt_slots.get(session_id)`；`wiring.build_prompt_context_from_metadata` 加
     `prompt_slots` 入参传给 `PromptContext`（鸭子读，core 不 import sdk）。
  5. `assemble_prompt_preview` 加 `prompt=PromptSlots`/`enabled_tools`（决策8 预览同源，PREVIEW 渲染）。
  6. `agent.sdk.__init__` 暴露新表面符号（Tool/ToolContext/HookAPI/PromptSlots/PromptText/LLMConfig 全家/SessionInfo/RunInfo/
     能力查询 DTO）——精确名单 `EXPECTED_SURFACE` 钉死留 R7。
- Rationale: 三段式扩张——旧 `product_profile` 路径 + `host_capabilities` 原样保留，全消费方/测试零改动；DTO 在 Kernel 边界处映射，
  core 不回引（无倒挂）。runtime slots 用内存 map 而非 metadata 持久化，因 PromptSlots 是 SDK 对象、且本就 per-session 由工厂重建。
- Evidence:
  - Tests: R3 wiring 契约 `tests/contract/test_sdk_kernel_wiring.py` 9 passed（含外部产品最小证明：包外 app 仅经 agent.sdk
    装配 + create_session + 闭包直连副作用工具一轮 + PromptSlots 进预览）；**全测试树 `pytest -m "not e2e"` = 2736 passed/1 skipped
    零回归**（DTO 返回类型变更涟漪过所有消费方干净）；ruff check + format 干净。
  - Entry: build_kernel 新签名 + create_session per-agent 经契约测试真装配 + 真跑一轮工具调用验证；CLI/PA live 留 R5/R6。
  - Frontend State Matrix / Browser QA / Visual: N/A
  - E2E/Regression: **R1 golden 7 + R2 skeleton-重现-golden 7 持续绿**（改 runtime 装配后字节零漂移，risk 1 守住）。
  - turn_id 断言（内部 RunRecord 字段、非 DTO、无产品消费）从 behavior contract 移除；whitelist runtime:172/kernel:141 行号锚定更新。
- Rollback: 接线 commit revert 回 building-blocks+list_* 态（旧 product_profile 路径独立可用）。
- Commits: C1=680f132b(新签名红测,rebase 保留) + list_*(076fbd57/fbdf1aa8 另 worker)；C2=<本次接线>；C3=<本条>。

## 新增范围（决策 12 ToolPresenter，base 更新后纳入 M1）

- orchestrator 把决策 12 加进 design.md（base = origin/main 0865584a 已含）：presenter 随 Tool 对象走、干掉 platform 全局
  `_PRESENTERS`/`register_presenter`/`resolve_presenter` + import 时 `_register_builtin_presenters()`，改 build_kernel 构
  `name→presenter` map 注入 realtime_stream hook（kernel 作用域）；`Tool` Protocol 加可选 `presenter`；`ToolPresenter`/
  `ToolPresentationEvent` 进 SDK 面（core 拥有、sdk re-export、闸2 豁免）；6 内置 presenter 挂工具类。
- 落点：① contracts.py Tool Protocol 补可选 `presenter` 字段；② sdk re-export ToolPresenter/ToolPresentationEvent；
  ③ 新 roadpoint「presenter 迁移」——先录 presentation golden 基线（6 自定义 + 默认回退）→ build_kernel 注入 kernel 作用域 map →
  删全局三件套 → 内置 presenter 挂类 → golden 守逐字节；④ 外部产品最小证明加码：副作用工具自带 presenter，断言 label/summary/
  detail 出现在 tool_start/tool_end。tasks.md 待补行。

## 后续 roadpoint（本 worker 独占续跑）

- R4：cron 迁出内核 + `HostCapabilityDispatcher`/`HostCapabilityContext`/`host_capabilities=`/`_inject_host_capabilities` 整组删
  + cron 闭包直连 `CronExecutionService`（保跨线程入队 + per-agent 路由）；PA tools/hooks/skills 物理目录搬 `src/personal_assistant/`。
- R-presenter（决策12，可与 R4 并列或紧随）：见上「新增范围」。
- R5：coding_cli 切新表面 + live（R-CLI-1/2/3）。
- R6：personal_assistant 工厂 `prompt_for`（拼 PromptSlots 四槽）+ main 装配 + 预览同源 + live（R-PA-1/2/3、R-CP-1/2/3、R-GW-3）。
- R7：products/ 解散 + bootstrap `_product_root` 退役 + 旧导出清零 + 决策7 三道闸（M1：所有权+豁免闸，豁免名单 = C1 三类
  [RunOrigin/PermissionDecision/TERMINAL_RUN_STATUSES] + ToolPresenter/ToolPresentationEvent[决策12] + `_M1_TEMP_REPORTER_EXPORTS`）。
- live-critical（cron/heartbeat/群聊运行时 + prompt 运行时装配 + presenter IM 渲染）需真端到端证据（§0.3/§0.11），env 起不来按 §0.11
  找 orchestrator，不自降证据。

## HANDOFF（R3 接线完成 + 决策12 排序定；R4 起精确入口）

- 状态：R3 接线实质完成并 push（local==origin==4e638b02，全测树 2736 passed/1 skipped 零回归，R1/R2 golden 14 绿，ruff 干净）。
  唯一 R3 缺口 = 决策12 presenter（归 R-presenter）。orchestrator 已 ack 排序：**先 R4 → 再 R-presenter**（两者都动 build_kernel
  工具装配,串行避免打架;R4 先把「原生工具目录进 build_kernel」骨干立稳,presenter 随对象自然叠上）。
- **R4 精确入口（已 grep 取证）**：
  - HostCapability 全消费点（整组删/改）：`agent/core/tools/{__init__,base,registry,host_capability}.py`、`agent/sdk/{__init__,kernel.py}`
    （kernel `_inject_host_capabilities` + `host_capabilities=` 参数 + legacy 路径传参 + __init__ 导出）、
    `personal_assistant/main.py:2106-2115`（`_cron_dispatcher` 构造 + `build_kernel(host_capabilities=_cron_dispatcher)`）、
    `personal_assistant/scheduler/gateway_cron_dispatcher.py`（`GatewayCronDispatcher(HostCapabilityDispatcher)`，整文件随删桥退役/改写成 cron 工具闭包持有的 service）、
    测试 `tests/contract/test_agent_sdk_surface_contract.py`、`tests/unit/personal_assistant/test_cron_scheduler_tick.py`、`test_cron_tool_openclaw.py`。
  - cron 工具迁移：`agent/products/personal_assistant/tools/cron.py` → `src/personal_assistant/tools/`；`run()` 闭包直接持有
    `CronExecutionService`（跨线程入队自 marshalling，参考现 `cron_execution_service.py:541` task.cancel 那条线程边界），不经内核回桥；
    保 per-agent 路由（现 GatewayCronDispatcher 按 agent_id 路由的语义要迁进闭包/工厂绑定）。
  - PA 物理目录搬家：`agent/products/personal_assistant/{tools,hooks,skills,prompt_sections.py,profile.py,defaults.py,toolsets.py}`
    → `src/personal_assistant/`（注意 import 边界:搬后 PA 工具/hook 由 PA 工厂经 build_kernel(tools=/hooks=) 传入,不再被内核扫目录）。
  - **live-critical（R-CP-2）**：cron 实跑 = 建 job→触发→执行→结果回投对应 agent 会话,需真端到端(./scripts/e2e-up.sh),不能只单测绿。
- **R-presenter 精确入口（决策12）**：
  - 现状:platform 全局 `agent/platform/tools/presentation.py`(`_PRESENTERS`/`register_presenter`/`resolve_presenter`/
    `_register_builtin_presenters()` import 副作用 + 6 presenter 类 + `_DefaultPresenter`)；realtime_stream
    `agent/platform/hooks/builtins/realtime_stream.py:7,46,65` import + 调 `resolve_presenter(name)`。
  - golden 基线已就位:`tests/unit/platform/tools/test_presentation.py`(6 presenter format_start/end + 默认精确断言)= 迁移前
    presentation 基线,**迁移中保留这些精确断言不动 = 逐字节守**;改的是 `_presenter(name)` 解析入口。
  - 拟用解析机制(待 orchestrator 最终 ack,默认采用):realtime_stream 从 `ctx.metadata["tool_registry"].get(name).presenter`
    解析(tool_registry 已由 registry.execute 注入 hook ctx,见 registry.py:128),无则落 `_DEFAULT`;**不**另造 build_kernel→setup
    注入 map(等价但更内聚)。core 留 `ToolPresenter`/`ToolPresentationEvent`(纯函数无 IO)→ sdk re-export(闸2 豁免);
    `Tool` Protocol(contracts.py)加可选 `presenter` 字段;6 presenter 类挂到各内置工具类 `.presenter`;删 platform 全局三件套。
  - 外部产品证明加码:`test_sdk_kernel_wiring.py` 的闭包副作用工具加 `.presenter`,断言 label/summary/detail 出现在 tool_start/tool_end。
- R5/R6/R7 见上「后续 roadpoint」;R7 豁免名单 = RunOrigin/PermissionDecision/TERMINAL_RUN_STATUSES + ToolPresenter/ToolPresentationEvent
  + `_M1_TEMP_REPORTER_EXPORTS`。
- 协调注记:本 worktree 曾发生双 worker 冲突,现已彻底理清——**单一所有者**,base 含决策12,4e638b02 是权威起点。续跑勿 reset 回更早 commit。

## R-presenter 完成（决策12 presenter 随 Tool 对象走，已 push）

- Context: 决策12——presenter 解析从 platform 模块级全局注册表(string-keyed + import 副作用)迁到「随 Tool 对象走、kernel 作用域解析」,
  与决策2「工具是产品全权拥有的原生对象」同根。orchestrator 确认排序 R4 内做、先录 golden 基线。
- Decision:
  1. 表面侧(已 push 53dcd864):Tool Protocol 文档化可选 `presenter`(getattr 读、非 required 成员不破 isinstance);
     ToolPresenter/ToolPresentationEvent re-export 进 agent.sdk(core 拥有、闸2 豁免)。
  2. golden 基线(C1,已 push):`tests/unit/platform/tools/test_presentation_golden.py` 逐字段快照 6 presenter + 默认(迁前录,13 passed)。
  3. 迁移(C2,本次):删 platform 全局 `_PRESENTERS`/`register_presenter`/`resolve_presenter`/`_register_builtin_presenters()` 整组;
     6 presenter 类保留(纯函数)实例化为 `*_PRESENTER` 单例;6 内置工具类各挂 `presenter = *_PRESENTER`;新 `resolve_presenter_for_tool(tool)`
     从 `tool.presenter` 读、缺省落 `_DEFAULT`;realtime_stream 改从 `ctx.metadata["tool_registry"].get(name).presenter` 解析。
- Rationale: 从 tool_registry(已装配工具事实源)读 `.presenter` 比 build_kernel 另注入平行 map 更内聚、无重复真相、外部产品工具自带
  presenter 自动可达、不加 build_kernel→setup 新通道(orchestrator 未否决,采用)。MCP/运行时发现工具无 presenter 落默认,与迁前一致。
- Evidence:
  - Tests: presenter 套件(test_presentation 23 + golden 13 + realtime_stream + cap)43 passed;**全测试树 2749 passed/1 skipped 零回归**;ruff 干净。
  - Entry: presenter 经 realtime_stream hook 在 tool_start/tool_end 发 presentation;真端到端 IM 渲染验证留 R6 live(IM 创建 agent 跑工具看卡片)。
  - E2E/Regression: presentation golden(迁前基线)逐字节守 IM 渲染零变化——迁后 resolve seam 改读 tool.presenter、期望值不动、全绿。
  - Browser QA / Visual: 待 R6 IM live 看工具卡片渲染。
- Rollback: C2 revert 恢复全局注册表;表面侧/golden 独立 commit 可分别 revert。
- Commits: 表面=53dcd864;golden C1=<presenter golden commit>;迁移 C2=<本次>;C3=<本条>。
- **外部产品 presenter 证明已加码(本次完成)**:`test_sdk_kernel_wiring.py::test_closure_tool_presenter_surfaces_in_stream`——
  闭包副作用工具自带 `presenter`(label=Record/summary=note=hi/detail),经 `kernel.stream` 真订阅,断言 presentation 出现在
  `tool_start`/`tool_end` 事件。这条**驱动真实解析链**(realtime_stream 从 ctx.tool_registry 读 .presenter,非内置工具走这条路),
  守住 orchestrator nail-down ①:防「ctx.tool_registry 不可达→静默落默认、纯函数断言照绿、漂移逃逸」。10 passed。

## [Design 实现路径等价替换] R-presenter: presenter 解析机制(§4 记一笔)

- design 字面: 决策12 写「`build_kernel` 时从工具目录构 `name→presenter` map 并注入 realtime_stream hook」。
- 实际采用: realtime_stream 从 `ctx.metadata["tool_registry"].get(name).presenter` 解析(tool_registry 由 registry.execute 既有
  注入 hook ctx),无则落 `_DEFAULT`。**不**构 build_kernel→setup 注入的平行 map。
- 等价性 + 决策12 四条绑定契约对照(design 那句是**实现机制描述,非契约**,orchestrator 确认):
  ① presenter 随 Tool 对象走 ✓(读 tool.presenter);② kernel 作用域解析非全局 ✓(读已装配 tool_registry,非模块级 global);
  ③ 删 platform 全局 `_PRESENTERS`/`register_presenter`/`resolve_presenter` ✓(整组删);④ golden 逐字节 ✓(test_presentation_golden 迁前基线 + 真实 hook 链证明)。
- 为何更优: 单一真相源(对象 `.presenter`)无平行 map、与决策4「解析来自已装配 Kernel」同构;外部产品工具自带 presenter 经
  `build_kernel(tools=)` 注册后自动可达,无须 build_kernel 额外收集。
- 影响范围: 仅实现路径(realtime_stream 解析方式),不影响决策12 任何对外契约;**design.md 不改**(design-author 所有权域,§0.3);
  delta-spec `specs/kernel/spec.md` 的「工具展示由工具自带的 presenter 决定」Requirement **本就按契约写**(随对象、自带 presenter 决定、
  无须额外注册步骤),不绑具体注入方式,**与本实现一致,无须校正**。reviewer/verifier 以 delta-spec 契约 + 本节为准,勿被 design 字面「构 map 注入」误导。

## R4 结构部分边界裁定(三段式:先迁后删)

- 取证:`agent.products.personal_assistant.*` + `host_capabilities=` 被 main.py(legacy PROFILE 路径)+ platform/products 垫片
  + sdk 导出 + ≈10 测试在用。**现在物理搬目录/删 HostCapability 会打断在用 PA + 红一大片**,这些消费者 R5/R6/R7 才消失。
- 裁定(三段式纪律,不改架构终态只改删除时机):
  - R4 余下做**扩张/迁移工具侧**:`src/personal_assistant/tools/` 新建闭包 cron 工具(`make_cron_tool(cron_svc)`,闭包持 service
    + per-agent 路由),经新 build_kernel(tools=) 可用;**不删** legacy cron.py/host_capabilities=/GatewayCronDispatcher。
  - R5/R6:CLI/PA 切新 build_kernel,消费者迁离 legacy 路径。
  - **R7 收缩段一次删干净**:PA 目录物理搬家 + HostCapabilityDispatcher/Context/host_capabilities=/_inject_host_capabilities 整组删
    + GatewayCronDispatcher 删 + products/ 解散 + bootstrap _product_root 退役 + SDK 撤导出 + 决策7 三道闸。
  - 理由:先删后破只能向前修、回退粒度归零(违反决策11);先迁后删每步独立可 revert、全程不破 PA。终点不变(products 没了/桥没了/PA 在 src/)。
- **orchestrator 认可此边界**(2026-06-14):决策11「三段式保回退粒度」的正确落地,非偏离——design 把 HostCapability 删除写 R4 是概念归类,
  按其自身三段式纪律删除本就落收缩段(R7)。两个 nail-down(收尾必守):
  1. **R7 删桥前必 grep 全仓确认零消费者**(不凭印象),删完全测树 + cron live 再绿一次。
  2. **桥/legacy 导出暂留期**,决策7 守卫的精确名单/豁免名单要容得下这些 legacy 导出——标 **M1 临时**
     (`_M1_TEMP_REPORTER_EXPORTS` 同类,或单列 legacy bridge 临时名单),收缩段(R7)同步移除,**别让守卫闸在扩张期就误红**。
  3. PA 物理目录搬家硬约束:`agent.products.personal_assistant.*` 被 legacy PERSONAL_ASSISTANT_PROFILE 路径 + ≈10 测试在用,
     搬家须在 R6 消费者切走后、或搬时留 re-export shim 保 legacy 不红,直到 R7 products 解散一并清。

- **orchestrator 精确化「物理搬家 = copy + delete 跨阶段拆开」(2026-06-14,关键,覆盖上面 #3 的「倾向 R7 一次搬」)**:
  「物理搬家」**不是**整体推到 R7,而是拆成两半跨阶段:
  - **扩张(R4):copy 长出 src/ 新位置**。PA 工厂需要的资产(`prompt_for` 逻辑 / hooks / skills / cron 闭包工具)**copy 进
    `src/personal_assistant/` 作为新代码长出**,旧 `agent/products/personal_assistant/` **原样留着**(legacy + ≈10 测试还在用),新旧并存全绿。
    **关键硬约束**:R6 的 PA 工厂 + main.py **只能 import `agent.sdk` 和自己包 `src/personal_assistant/`,绝不能 import `agent.products`**
    (模块边界硬规则)——所以 R6 要用的 `prompt_for`/hooks **必须在扩张期(R4)就 copy 进 src/**,否则 R6 无合法 import 来源。这是「长出」,
    必须在扩张做,**不能等收缩**。cron 已是新形态(`src/personal_assistant/tools/cron.py` make_cron_tool),符合此规则。
  - **迁移(R5/R6)**:main.py / CLI 切新 build_kernel,用 src/ 里的副本。
  - **收缩(R7):delete 旧位置**。grep 零消费者后删 `agent/products/personal_assistant/` + platform/products 垫片 + 桥 + 全局
    presenter + 撤 SDK 导出。
  - **≈10 个 import `agent.products.personal_assistant` 内部的测试**:测的是正在解散的旧产品层。R7 删 products/ 时逐个**重定向**到
    新 src/ 等价物或内核契约、或**删除**(若测已消除的内部实现),**逐个记 progress.md 给理由,不许放任红**。属 R7 收缩。
  - 口径:扩张=copy 长出 src/(新旧并存全绿);迁移=切消费者;收缩=删旧 + 迁测试。依据决策11 + 模块边界硬规则。
  - **R4 待做(copy 长出,本 worker 未做,留续做)**:`src/personal_assistant/product.py` 的 `prompt_for(agent)` 拼 PromptSlots 四槽——
    **现成配方 = R2 golden 测试 `tests/integration/test_kernel_skeleton_reproduces_golden.py::_pa_slots(ctx)`**:head=identity+runtime;
    body=heartbeat/cron/cron_routing/platform_policy/guidelines/routing;custom=user_custom;tail=communication_context。段文本需从
    `agent/products/personal_assistant/prompt_sections.py` 的 `_PA_*` 段 copy/重derive 进 src/(byte-identical,golden 守);PA hooks(chat_history)
    + skills 同样 copy 进 src/。这块是 R6 PA 工厂的「长出」半,与 main.py 切装配同属一个逻辑单元,建议 R6 worker 一气做。

## R4 cron 闭包工具完成(扩张段,已 push)

- 做完:`src/personal_assistant/tools/cron.py` + `make_cron_tool(cron_services)` 工厂(闭包持 agent_id→CronExecutionService 映射,
  _action_run 按 agent_id 路由直连 enqueue,无 HostCapabilityDispatcher);job 持久化/description/schema 逐字 port 自旧 tool(零行为漂移)。
- 测试 `tests/unit/personal_assistant/test_cron_tool_closure.py` 5 passed(roundtrip/路由/per-agent隔离/缺service error/declined ack);
  全树 collect 2760 干净;ruff 干净。legacy `agent/products/.../cron.py` + host_capabilities= + GatewayCronDispatcher 暂留(R7 删)。
- **决策9 三不变量已核(代码契约,orchestrator nail-down)**:① 工具行为——list/add/update/remove/runs 逐字 port,closure 测试 roundtrip 绿;
  ② 跨线程入队 marshalling——`make_cron_tool` 的 run() 由内核经 `asyncio.to_thread` 调用(worker 线程),直接调 `service.enqueue`,
  enqueue 内部 Context B 用 `call_soon_threadsafe` 把 coro 投到 gateway_loop(cron_execution_service.py 既有逻辑,闭包未绕过);
  ③ per-agent 路由——按 `ctx.session_metadata["agent_id"]` 路由到 `cron_services[agent_id]`(test_run_per_agent_isolation 证 A 的 run 不碰 B)。
  cron verbatim golden(test_cron_prompt_sections)绿。
- **仍待 R4 live(留 R5/R6,因依赖 R6 PA 工厂 wiring)**:R-CP-2 cron 实跑——make_cron_tool 经 PA 工厂传入 build_kernel 后(R6),
  建 job→触发→执行→结果回投对应 agent 会话,真起 IM+Gateway(./scripts/e2e-up.sh)跑到用户可见结果。
- **presenter 全局三件套即时删确认(orchestrator 自我纠正后,A 终定)**:rewire 后零剩余消费者(realtime_stream 改读 tool.presenter、内置已挂类),
  全测树绿证明新路径完全替代,即时删干净安全。**不留 fallback 死代码**。
  - **为何 presenter 删得早、桥/products 延后(给 reviewer)**:presenter 全局注册表的消费者**仅 2 处**(realtime_stream + 2 测试文件),
    可在**同一 commit 原子迁完**——「迁」与「删」同时发生不违反「先迁后删」(没删在用的);而 HostCapability 桥 / products 被 ≈10 个 legacy
    测试 + PERSONAL_ASSISTANT_PROFILE 路径困住,无法同步迁,故删除延后到 R7 收缩段。**判据是「消费者能否同 commit 迁完」,不是 roadpoint 标签**。
  - **robustness 双重兜底(关闭「静默落默认漂移」担忧)**:① tool_registry 由 registry.execute 每次工具调用必注入(主路径必达);
    ② `.get(name)` 返 None(工具不在 registry)→ _DEFAULT;③ 工具在 registry 但无 `.presenter`(None)→ _DEFAULT。MCP / .nano 运行时
    发现工具天然走 ②/③ 落默认,**与旧全局注册表时代完全一致**(它们本就不在 _PRESENTERS)。无「有自定义 presenter 但对象路径不可达」的工具。
    决策7 豁免名单**不为全局三件套留位**(已不存在)。

## HANDOFF — 剩余 R5/R6/R7(live-critical,建议新会话续)

> 状态:R3 接线 + 决策12 presenter(含真实 hook 链证明)+ R4 cron 闭包工具全部 committed+pushed,branch 绿,全树 collect 2760。
> 现场干净可无缝接力。下面是剩余三个 roadpoint 的精确续做入口。本会话已扛过双 worker 冲突恢复 + 上述大块,上下文吃紧,
> R5/R6 live-critical(真起服务、e2e、截图)建议新会话以充足预算续做,§0.11:env 起不来找 orchestrator,不自降证据。

- **R5 — coding_cli 切新表面 + live**:
  - 入口:`src/coding_cli/commands.py`(现 `build_kernel(product_profile=LOCAL_CODING_PROFILE, llm_config=…)` + `create_session(skills=/tool_allowlist=)`)。
    切到新 `build_kernel(llm=LLMConfig.from_env(), tools=[原生工具目录], hooks=[…], can_use_tool=terminal_prompt, workspace_config_dirname=".nanocode")`
    + `create_session(enabled_tools=…, features=…, prompt=PromptSlots)`。需建 coding_cli 默认工厂(`src/coding_cli/product.py`,见 design §A 示意)。
  - live(§0.3):R-CLI-1 工具调用任务、R-CLI-2 选模型启动、R-CLI-3 `/model` 热切换。`PYTHONPATH=src python3 -m coding_cli.main`。
  - golden 守:CLI prompt 走 PromptSlots 后必跑 `test_full_system_prompt_byte_identical`(lc_full 场景)。
- **R6 — PA 工厂 + main 装配 + 预览同源 + live**:
  - 入口:`src/personal_assistant/main.py:2094-2117`(legacy build_kernel)。切新 build_kernel(tools 含 `make_cron_tool(cron_services)`
    + send_message/web_search 等 PA 工具迁入后传入,hooks=PA hooks,workspace_config_dirname=".nanoassistant")。建 PA 工厂
    `src/personal_assistant/product.py` 的 `prompt_for(agent)` 拼 PromptSlots 四槽(cron/heartbeat→body,群聊→tail,见 design §B + R2 golden 的 _pa_slots 映射)。
    cron_services 映射从现 GatewayCronDispatcher._services 取(map 共享引用,晚注册可见);此时 PA 不再传 host_capabilities=。
  - 预览同源:PA 预览 provider 用同一 prompt_for 构造 PromptSlots 调 `kernel.assemble_prompt_preview(prompt=…, features=…, enabled_tools=…, scenario=…)`。
  - live(§0.3):R-PA-1/2/3、R-CP-1 heartbeat(守 K2.6 不返 HEARTBEAT_OK)、R-CP-2 cron 实跑、R-CP-3 群聊@、R-GW-3 会话档案落位。
  - golden 守:PA 装配走 PromptSlots 后必跑 `test_full_system_prompt_byte_identical`(pa_* 场景)。
- **R7 — 收缩 + 决策7 三道闸**:
  - products/ 解散:`agent/products/` 整目录删 + `agent/platform/products/` 垫片删 + bootstrap `_product_root()` 退役 + SDK 撤
    LOCAL_CODING_PROFILE/PERSONAL_ASSISTANT_PROFILE 导出;PA tools/hooks/skills/prompt_sections 物理搬 src/personal_assistant/(R6 已建工厂引新位置)。
  - HostCapability 整组删:`agent/core/tools/host_capability.py` + base/registry/__init__ 的 host_capabilities 字段 + kernel `_inject_host_capabilities`
    + `host_capabilities=` 参数 + GatewayCronDispatcher + SDK 撤 HostCapabilityDispatcher/Context 导出;legacy cron.py 删。
  - build_kernel 收缩:删 legacy `product_profile=`/`llm_config=` 路径(消费者已全迁),只剩新签名。
  - 决策7 三道闸(M1 闸):① 精确名单 `EXPECTED_SURFACE` 暂含 reporter 旧导出(M2 落最终闸);② 所有权闸(导出 __module__ sdk-owned);
    ③ 豁免名单逐字钉死 = RunOrigin/PermissionDecision/TERMINAL_RUN_STATUSES(C1)+ ToolPresenter/ToolPresentationEvent(决策12)
    + `_M1_TEMP_REPORTER_EXPORTS`(SkillRegistry/ConfigResolver/default_skill_search_roots/FEATURE_REGISTRY/model registry 列表函数,M2 删)。
  - 全测试树 `pytest -m "not e2e"` 全收集绿是硬退出标准。

## R5 完成 — coding_cli 切新 build_kernel 2 层表面 + product.py 工厂 + live(已 push）

- Context: 三段式迁移段。coding_cli 切离 legacy `build_kernel(product_profile=LOCAL_CODING_PROFILE, llm_config=…)`
  到新 2 层表面 `build_kernel(llm=LLMConfig, tools=…, can_use_tool=…, workspace_config_dirname=".nanocode")` +
  `create_session(enabled_tools/features/prompt=PromptSlots)`。coding_cli 仅 import `agent.sdk` + 自己包（边界硬规则）。
- Decision（落点）:
  1. 新建 `src/coding_cli/product.py`（消费者默认工厂，SDK 不感知）:
     - `build_cli_kernel(llm, can_use_tool, repo_root)` → `build_kernel(llm=, tools=_build_self_evolution_tools(...), hooks=[], can_use_tool=, workspace_config_dirname=".nanocode")`。
     - `_build_self_evolution_tools(repo_root)` 构造 `SkillManageTool(skill_root=<root>/.nanocode/skills, registry=SkillRegistry(...))` + `MemoryTool()`
       放进 `tools=`——base 路径 `register_builtin_tools` 只注册 7 内置（read/write/edit/bash/agent/task_stop/web_fetch），
       memory/skill_manage 需路径解析参数，由工厂构造（决策 2：工具是产品全权拥有的原生对象，镜像 legacy bootstrap self-evolution 接线）。
     - `cli_prompt_slots()` 拼 LC PromptSlots（head=[lc.identity]、body=[lc.tools_footer, lc.guidelines]）,lc.* 文案逐字 port
       自 `products/local_coding/prompt_sections`（LC 无群聊/heartbeat/cron/custom，只 head+body 两槽）。
     - `open_cli_session(kernel, workspace_root)` → `create_session(enabled_tools=DEFAULT_ENABLED_TOOLS, features={memory_curation,skill_creation}, prompt=cli_prompt_slots(), metadata={"workspace_config_dirname":".nanocode"})`——
       threads workspace_config_dirname 进 session metadata 供 MemoryTool 派生 per-session memory_root（base 路径 SessionService 无 default_session_metadata）。
  2. `commands.py::_build_kernel` 切新路径:`LLMConfig.from_payload(_build_llm_config_payload(args), api_key=, timeout_seconds=)` 构 SDK LLMConfig（带 catalog,供 /model + list_models）+ `build_cli_kernel(...)`；
     3 个 `create_session(workspace_root=)` 调用点（--text / REPL 首启 / /new）全走 `open_cli_session`；删 legacy `_build_llm_config_from_args`。
  3. `dto.py`:新增 `LLMConfig.from_payload(payload, *, api_key, timeout_seconds)`——把 `LLMConfigPayload`（catalog）转 SDK `LLMConfig`，
     active 连接从 default_model + 其 owning provider 解析。
  4. `sdk/__init__`:re-export `MemoryTool`/`SkillManageTool`（决策 2 consumer 工厂构造路径解析工具）。
  5. CLI 测试 stub `create_session` 加 `**kwargs` 容新入参（`_cli_kernel_stubs.py`、`test_cli_async_repl_sdk.py`）。
- Rationale: 三段式迁移——LC prompt 文案 copy 进 src/coding_cli/（R7 删 products/ 时旧位置一并清，先迁后删保回退粒度）。
  base 路径已自动注册 7 内置工具,工厂只补 memory/skill_manage 两个路径解析工具,不重复装配。LLMConfig.from_payload 保 /model 热切换 + list_models 的 catalog 来源。
- Evidence:
  - Tests: lc_full golden 逐字节 **MATCH**（`cli_prompt_slots()` + `build_kernel_prompt_skeleton()` == golden_prompts/lc_full.txt）;
    CLI 单测 85 passed（test_cli_async_repl_sdk / repl_commands / text_sse / mode / repl_input / refactor_boundaries）;
    契约+golden 46 passed（surface_contract / kernel_wiring / two_layer_assembly / byte_identical / skeleton_reproduces_golden）;ruff 干净。
    冒烟装配:工具目录含 memory + skill_manage,get_llm_config 正常。
  - **Entry / live（§0.3 真端到端跑到用户可见结果，非 stub）**:
    - **R-CLI-1 工具调用任务 PASS**:`python3 -m coding_cli.main --text "Create hello.txt containing refactor406-live-ok ..."`（kimiCoding:K2.6，
      workspace .nanocode/config.yaml 设 dangerously_skip_permissions 自动批准）→ 真起会话 sess_099c828b、write 工具真调用
      （tool_start/tool_end 带 presenter label="Write"/summary="created (19 bytes)"）、**文件真写出内容 `refactor406-live-ok`**、run completed。
      证明:新 build_kernel 路径真跑工具调用 + per-session PromptSlots 装配 + presenter 实时渲染全 live 可用。
    - **R-CLI-2 选模型启动 PASS**:`--provider anthropic --model codex_oauth:gpt-5.5 --text "..."` → 正常启动跑出 `model-select-ok`，
      无需迁移配置/改启动参数;`get_llm_config().model == codex_oauth:gpt-5.5` 确认 --model 流到 active 连接。
    - **R-CLI-3 /model 热切换 PASS**:`reconfigure_llm(model=…)` 路径（CLI `llm-config set --model codex_oauth:gpt-5.5`，即 /model 热切机制）
      → 起于 kimiCoding:K2.6、切到 codex_oauth:gpt-5.5、kernel `get_llm_config()` 即时反映新 model;后续轮用新 active model（单一真相源更新）。
  - E2E/Regression: R1 golden(lc_full) + R2 skeleton-重现-golden 持续守,切表面后字节零漂移。
- Rollback: R5 commit revert 回 legacy product_profile 路径（独立可用）。
- Commits: C2=4ed79b0a（product.py + commands 切表面 + dto.from_payload + sdk re-export + stub 适配）。
