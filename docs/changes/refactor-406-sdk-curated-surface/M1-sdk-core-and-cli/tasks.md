# refactor-406-M1: sdk-core-and-cli — Tasks

> 对齐: ../design.md（决策 1/2/3/5/6/8/9 全落 M1）

## 目标

`agent.sdk` 从「内核装配入口 + core/platform/products 内部对象转发出口」收敛为产品中立的 2 层装配契约：`build_kernel(共享基座)` + `create_session(per-agent)` + `list_*` 中立查询，出入参全 SDK-owned DTO；`agent/products/` 解散下沉到 `coding_cli` / `personal_assistant` 工厂；cron 迁出内核、`HostCapabilityDispatcher` 整组删除；prompt 经内核模板骨架 + `PromptSlots` 四槽组装、产品文案逐字节复现现状。决策 7 守卫脚手架立（所有权 + 豁免闸，精确名单暂含 reporter 旧导出待 M2）。

外部可观察：CLI / PA / cron / heartbeat / 群聊 / prompt 预览所有用户旅程行为不变（reviewer 矩阵 R-CLI/PA/CP/GW/NEW 逐条实测）；发往 LLM 的 system prompt 逐字节与重构前一致（worker golden 守）。

## 退出标准

- [x] 2 层入口 `build_kernel`（共享基座）+ `create_session`（per-agent）+ `list_models/tools/features/skills`（内核侧产出）可用且有单测 — R3 接线完成（`test_sdk_kernel_wiring` / `test_kernel_list_capability_queries`）
- [x] 外部产品最小证明：测试内构造 agent 包外应用，仅经 `agent.sdk` 装配 + 开会话跑通带工具调用一轮（含闭包直连自己服务的副作用工具）— `test_sdk_kernel_wiring`（含闭包副作用工具 + presenter）
- [x] PA/LC 完整 system prompt 重构前 vs 重构后逐字节等价 — `test_full_system_prompt_byte_identical`（6 pa_* + lc_full）+ `test_kernel_skeleton_reproduces_golden`，cron/heartbeat/群聊三段经 `prompt_for` PromptSlots 复现，14 绿
- [x] 迁 cron 出内核前先补 cron 段逐字节 golden — `test_cron_prompt_sections` 升级 verbatim（R1）
- [x] sdk/prompt/llm/cron/dto 域旧导出清零（除 `_M1_TEMP_REPORTER_EXPORTS`）、`HostCapabilityDispatcher`/`host_capabilities=` 删除、cron 闭包直连 `CronExecutionService` — HostCapability 整组删 + CronServiceRegistry + `make_cron_tool` 闭包（R4/R7）
- [x] 决策 7 守卫脚手架立（所有权 + 豁免闸绿；精确名单暂含 reporter 旧导出 + PA/LC profile，标 `_M1_TEMP`，待 M2 落最终闸）— `test_agent_sdk_surface_guard`（3 闸）
- [x] `coding_cli` 仅 import 新表面 — `test_agent_sdk_boundary_contract` 绿（零 agent.core/platform/products 内部 import）
- [x] 全测试树 `pytest -m "not e2e"` 全收集绿 — 2745 passed / 1 skipped 零回归

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  1. PA/LC 完整 prompt 逐字节等价（重构前后）→ golden 等价测试，先录基线快照
  2. cron 段逐字节 golden（先补，迁移前防线）
  3. 2 层装配 + create_session per-agent 配置（enabled_tools/features/prompt 槽）行为
  4. list_models/tools/features/skills 返回 SDK-owned DTO、与运行时一致、跨 workspace skill 不混用
  5. 出入参 DTO（SessionInfo/RunInfo/LLMConfig）字段语义不变
  6. Tool/ToolContext/HookAPI Protocol：鸭子结构对象可装配、副作用工具闭包直连无内核回桥
  7. 外部产品最小证明（包外应用经 sdk 装配 + 工具调用一轮）
  8. cron 行为：工具行为 + 跨线程入队语义 + per-agent 路由，迁移前后一致
  9. 决策 7 守卫：精确名单闸（`__all__ == EXPECTED_SURFACE`）+ 所有权闸（`__module__` sdk-owned，豁免名单逐字钉死）
  10. assemble_prompt_preview 同源（预览 = 真实会话装配）
- 已有测试在：
  - golden：`tests/integration/test_prompt_sections_golden.py`、`tests/unit/agent/prompt_sections/test_prompt_sections_golden_baseline.py`（扩展为完整 prompt 逐字节 + 录重构前快照）
  - cron 段：`tests/unit/personal_assistant/test_cron_prompt_sections.py`（升级 len>20 → verbatim）
  - heartbeat verbatim：`tests/unit/personal_assistant/test_heartbeat_prompt_openclaw.py`（已有，保留）
  - 群聊 verbatim：`tests/unit/personal_assistant/test_communication_context.py`（已有，保留）
  - 表面守卫：`tests/contract/test_agent_sdk_surface_contract.py`（重写）+ `test_agent_sdk_boundary_contract.py`（保留方向守卫）
  - 2 层装配 / Protocol / DTO / 外部产品最小证明：新建 `tests/contract/test_sdk_two_layer_assembly.py`（理由：现有 surface contract 测旧 build_kernel 签名，2 层契约是新行为面，独立文件便于 reviewer 定位；不与旧文件混）
  - cron 行为：`tests/unit/personal_assistant/test_cron_tool_openclaw.py`（扩展，迁后改 import 路径）
- 落层/目录/marker：tests/unit（prompt 段 / DTO / 工厂）、tests/contract（守卫 / 2 层契约 / 外部产品证明）、tests/integration（完整 prompt golden）；marker：无（不需真进程）
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：重构前 prompt 快照（若以临时 fixture 文件形式录，最终内联进 golden 测试或留 fixture 由 golden 长期消费——保留有回归价值的，删一次性脚本）；live 实测日志/截图记 progress.md 不进套件
- 前端 UI：N/A（本 milestone 无前端改动；prompt 预览 IM 契约不变，前端不动）

## Roadpoints

> 三段式：R1-R2 录防线（golden 先行）→ R3-R6 建新表面 + 迁移 → R7 收缩 + 守卫落闸。每步独立 commit 可 revert。

### R1 — cron 段逐字节 golden + 完整 prompt 重构前基线快照  [DONE]

- 步骤：升级 `test_cron_prompt_sections` 把 `len>20` 弱断言改为 cron 段（pa.cron / pa.cron_routing）逐字节 verbatim 断言；录 PA（含 cron/heartbeat/群聊各配置组合）+ LC 完整 system prompt 重构前快照作 golden 基线。
- 验证：新 golden 测试在重构前代码上全绿（基线锁定）；cron verbatim 断言钉死现文案。
- 结果：DONE（C1=85a5d63c）。7 golden + cron/cron_routing verbatim，14 passed。

### R2 — 内核模板骨架 + PromptSlots 四槽（扩张，旧路径不动）  [DONE]

- 步骤：在 `agent/core/agent/prompt_sections/` 立产品中立模板骨架（按字节真相：head → core 规则 → body → 通用 feature 指引 → 背景/footer → custom → 易变尾部 → tail）；SDK 新增 `PromptSlots(head/body/custom/tail)` / `PromptText` 冻结值对象；内核装配 = 骨架 + 四槽填入。旧 `prompt_sections_builder` 路径暂留。
- 验证：用 R1 基线驱动——经新骨架 + PromptSlots（PA/LC 文案填槽）装配的 prompt 与基线逐字节一致。
- 结果：DONE（C1=e64b5a96 红测, C2=e7133b5c 实现）。skeleton 重现 golden 7 场景全绿，零回归。⚠️ 发现 design §251 骨架顺序 prose 与字节真相不符，按字节真相搭并报备 orchestrator（见 progress [Design 修订] §R2）。

### R3 — build_kernel 基座 + create_session per-agent + DTO + Protocol（扩张）  [DONE]

- 步骤：重构 `build_kernel(llm, tools, hooks, can_use_tool, workspace_config_dirname, repo_root)` 建共享基座（去 `product_profile`）；`create_session(workspace_root, enabled_tools, features, prompt=PromptSlots, title, metadata)` 返回 `SessionInfo`；`submit/get_run/cancel`→`RunInfo`；`get_llm_config/reconfigure_llm`→`LLMConfig` DTO（含 `from_env()`，注册表内部初始化）；`Tool`/`ToolContext`/`HookAPI` SDK-owned Protocol。`list_models/tools/features/skills` 返回 SDK-owned DTO。
- 结果：DONE。building blocks（dto.py C1=d3b6b29d/C2=7b90ae84）+ kernel 接线（双签名 build_kernel / create_session per-agent / DTO 化 / list_* / runtime 骨架+slots 装配 / 外部产品最小证明）全完成。`test_sdk_kernel_wiring` 9 + `test_kernel_list_capability_queries` 4 + `test_sdk_two_layer_assembly` 绿；含闭包副作用工具 + presenter 真实 hook 链证明。（注：决策3 memory/skill_manage 内核内置注册的 base 缺口在收口补正中补全——见 progress.md「补正1」。）

### R4 — cron 迁出内核 + HostCapabilityDispatcher 删除（迁移）  [DONE]

- 步骤：PA 工具（cron/send_message/web_search）迁 `src/personal_assistant/tools/`；cron `run()` 闭包直连 `CronExecutionService`（跨线程入队，按 agent_id 路由），删 `HostCapabilityDispatcher`/`HostCapabilityContext`/`build_kernel(host_capabilities=)`/`_inject_host_capabilities`。
- 结果：DONE。`make_cron_tool(cron_services)` 闭包（R4 扩张）+ HostCapability 整组删 + `GatewayCronDispatcher`→`CronServiceRegistry`（R7 收缩）。`test_cron_tool_closure` 5 + `test_cron_scheduler_tick` 绿；`test_cron_coding_cli_isolation` 绿；**live cron 实跑回投 PASS**（建 job→触发→执行→结果路由回会话，删桥后复验绿，progress.md R-CP-2）。

### R5 — coding_cli 切新表面（迁移）  [DONE]

- 步骤：`coding_cli` 建默认工厂 `src/coding_cli/product.py`（仅 import `agent.sdk` 新表面：build_kernel 基座 + create_session + PromptSlots），`/model` 走 `reconfigure_llm`（LLMConfig DTO）。
- 结果：DONE。`build_cli_kernel` + `open_cli_session` + `cli_prompt_slots`；commands.py 切新 build_kernel（`LLMConfig.from_payload` 带 catalog）。**live PASS**：R-CLI-1 工具调用（文件真写）/ R-CLI-2 选模型 / R-CLI-3 `/model` 热切（progress.md）；lc_full golden 逐字节 MATCH；boundary contract 绿。

### R6 — personal_assistant 切新表面 + prompt 工厂（迁移）  [DONE]

- 步骤：`personal_assistant` 建默认工厂 `src/personal_assistant/product.py`（`build_pa_kernel` + `prompt_for(agent, scenario)` 拼 PromptSlots：cron/heartbeat→body、群聊→tail），main 装配切 build_kernel 基座 + create_session；预览 provider 用同一 `prompt_for`。reporter 暂留旧 import（M2 切）。
- 结果：DONE。**live PASS**：R-PA-1 发消息 / R-PA-3 权限卡 park / R-CP-1 heartbeat（K2.6 不返死反射）/ R-CP-3 群聊 @ / R-GW-3 JSONL per-workspace / R-CFG-4 预览同源（progress.md）；6 个 pa_* golden 逐字节 MATCH。R-PA-2 IM 离线自治归 reviewer 矩阵（共享路径论证见 progress.md）。**live 暴露并修 3 真 bug**：LLMConfig.from_payload / RunInfo.start_sequence / shim 共享 live pipeline._agents。

### R7 — 收缩 + 决策 7 守卫落闸  [DONE]

- 步骤：删桥 + legacy 路径 + 决策7 三道闸；products/ 物理解散延 M2（reporter 依赖，orchestrator 裁定，design §223）。
- 结果：DONE。删 HostCapability 整组 + legacy products cron.py + build_kernel legacy `product_profile=` 路径（4 测试迁新 `llm=` 签名）；`GatewayCronDispatcher`→`CronServiceRegistry`。决策7 三道闸 `test_agent_sdk_surface_guard`：精确名单（`__all__ == EXPECTED_SURFACE` 38 符号）+ 所有权闸 + 豁免名单（C1 三类 + ToolPresenter/Event + `_M1_TEMP_REPORTER_EXPORTS` + `_M1_TEMP_PROFILES`，显式分组标 M1 临时）。≈10 个 import agent.products 内部的测试逐个重定向/删（理由记 progress.md）。**全测树 `pytest -m "not e2e"` 2745 passed/1 skipped + cron live 复验绿**。
- **归 M2**：reporter→`Kernel.list_*` + products/ 物理删 + 撤 `_M1_TEMP` 豁免（reporter 旧导出 + PA/LC profile）+ bootstrap `_product_root` 退役 + 决策7 精确名单落最终闸。
