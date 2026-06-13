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
