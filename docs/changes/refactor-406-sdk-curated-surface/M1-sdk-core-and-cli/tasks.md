# refactor-406-M1: sdk-core-and-cli — Tasks

> 对齐: ../design.md（决策 1/2/3/5/6/8/9 全落 M1）

## 目标

`agent.sdk` 从「内核装配入口 + core/platform/products 内部对象转发出口」收敛为产品中立的 2 层装配契约：`build_kernel(共享基座)` + `create_session(per-agent)` + `list_*` 中立查询，出入参全 SDK-owned DTO；`agent/products/` 解散下沉到 `coding_cli` / `personal_assistant` 工厂；cron 迁出内核、`HostCapabilityDispatcher` 整组删除；prompt 经内核模板骨架 + `PromptSlots` 四槽组装、产品文案逐字节复现现状。决策 7 守卫脚手架立（所有权 + 豁免闸，精确名单暂含 reporter 旧导出待 M2）。

外部可观察：CLI / PA / cron / heartbeat / 群聊 / prompt 预览所有用户旅程行为不变（reviewer 矩阵 R-CLI/PA/CP/GW/NEW 逐条实测）；发往 LLM 的 system prompt 逐字节与重构前一致（worker golden 守）。

## 退出标准

- [ ] 2 层入口 `build_kernel`（共享基座）+ `create_session`（per-agent）+ `list_models/tools/features/skills`（内核侧产出）可用且有单测
- [ ] 外部产品最小证明：测试内构造 agent 包外应用，仅经 `agent.sdk` 装配 + 开会话跑通带工具调用一轮（含闭包直连自己服务的副作用工具）
- [ ] PA/LC 完整 system prompt 重构前 vs 重构后逐字节等价（基线 = 重构前快照；cron/heartbeat/群聊三段经 PromptSlots 四槽复现）
- [ ] 迁 cron 出内核前先补 cron 段逐字节 golden（现 `test_cron_prompt_sections` 仅 `len>20` 弱断言）
- [ ] sdk/prompt/llm/cron/dto 域旧导出清零（除 M1 临时保留的 reporter 旧导出，标注 `_M1_TEMP_REPORTER_EXPORTS`）、`HostCapabilityDispatcher`/`host_capabilities=` 删除、cron 闭包直连 `CronExecutionService`
- [ ] 决策 7 守卫脚手架立（所有权 + 豁免闸绿；精确名单暂含 reporter 旧导出，待 M2 落最终闸）
- [ ] `coding_cli` 仅 import 新表面
- [ ] 全测试树 `pytest -m "not e2e"` 全收集绿

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

### R3 — build_kernel 基座 + create_session per-agent + DTO + Protocol（扩张）

- 步骤：重构 `build_kernel(llm, tools, hooks, can_use_tool, workspace_config_dirname, repo_root)` 建共享基座（去 `product_profile`）；`create_session(workspace_root, enabled_tools, features, prompt=PromptSlots, title, metadata)` 返回 `SessionInfo`；`submit/get_run/cancel`→`RunInfo`；`get_llm_config/reconfigure_llm`→`LLMConfig` DTO（含 `from_env()`，注册表内部初始化）；`Tool`/`ToolContext`/`HookAPI` SDK-owned Protocol。`list_models/tools/features/skills` 返回 SDK-owned DTO。
- 验证：新 `test_sdk_two_layer_assembly.py` 覆盖 2 层装配、enabled_tools 子集、features 门控、Protocol 鸭子结构、DTO 字段、list_* 一致性 + 跨 workspace skill；外部产品最小证明（含闭包副作用工具）跑通带工具调用一轮。

### R4 — cron 迁出内核 + HostCapabilityDispatcher 删除（迁移）

- 步骤：PA 工具（cron/send_message/web_search）+ hooks + skills 物理目录从 `agent/products/personal_assistant/` 迁 `src/personal_assistant/`；cron `run()` 闭包直连 Gateway `CronExecutionService`（`call_soon_threadsafe` 跨线程入队，按 agent_id 路由），删 `HostCapabilityDispatcher`/`HostCapabilityContext`/`build_kernel(host_capabilities=)`/`_inject_host_capabilities`。
- 验证：cron 单测（迁后路径）+ per-agent 路由 + 跨线程入队语义绿；contract `test_cron_coding_cli_isolation` 绿；live cron 实跑回投（Evidence）。

### R5 — coding_cli 切新表面（迁移）

- 步骤：`coding_cli` 建默认工厂（品牌 + per-agent 默认），仅 import `agent.sdk` 新表面（build_kernel 基座 + create_session + PromptSlots），`/model` 走 `reconfigure_llm`（LLMConfig DTO）。
- 验证：CLI 带工具调用任务 + 选模型启动 + `/model` 热切换 live 实跑（Evidence）；`coding_cli` 仅 import 新表面（boundary contract 绿）。

### R6 — personal_assistant 切新表面 + prompt 工厂（迁移）

- 步骤：`personal_assistant` 建默认工厂（`build_pa_kernel` + `prompt_for(agent)` 拼 PromptSlots：cron/heartbeat→body、群聊→tail），main 装配切 build_kernel 基座 + create_session；预览 provider 用同一 `prompt_for`。reporter 暂留旧 import（M2 切）。
- 验证：PA 发消息 + 权限卡 + heartbeat + 群聊 @ live 实跑（Evidence）；预览同源测试（预览=真实会话 byte-identical）；R1 完整 golden 逐字节绿。

### R7 — 收缩 + 决策 7 守卫落闸

- 步骤：删 `agent/products/`（解散）+ bootstrap `_product_root()` 扫描 + 旧 sdk 导出（sdk/prompt/llm/cron/dto 域，除 `_M1_TEMP_REPORTER_EXPORTS`）；重写 `test_agent_sdk_surface_contract`：精确名单闸（`__all__ == EXPECTED_SURFACE`）+ 所有权闸（`__module__` sdk-owned，豁免名单 = C1 三类 + `_M1_TEMP_REPORTER_EXPORTS` 显式分组）+ typing 别名特殊处理。删迁移期红测/失效旧测。
- 验证：三道闸绿；全测试树 `pytest -m "not e2e"` 全收集绿。
