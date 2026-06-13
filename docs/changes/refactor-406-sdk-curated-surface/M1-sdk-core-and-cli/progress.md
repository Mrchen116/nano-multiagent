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
- Commits: C1=<填>
