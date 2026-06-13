# refactor-406-M1 — Progress

## 启动对齐（§2.5）

- 已读：motivation.md / design.md（决策 1/2/3/5/6/8/9）/ kernel delta-spec / kernel.py / bootstrap.py / products/base.py / PA profile+prompt_sections / core_sections.py / base.py（prompt 装配）/ feature_registry.py / wiring.py / host_capability.py / cron.py / surface contract / TESTING_GUIDE + 消费者调用点。
- 基线：`pytest -m "not e2e"` 2697 passed / 2 skipped 全绿。
- orchestrator 答复（team-lead）：
  - Q1：M1 所有权闸真立起来并绿；暂留 reporter 旧导出（SkillRegistry/ConfigResolver/default_skill_search_roots/FEATURE_REGISTRY/model registry 列表函数）走豁免名单临时扩容，显式标注 `_M1_TEMP_REPORTER_EXPORTS`，与 C1 永久豁免（RunOrigin/PermissionDecision/TERMINAL_RUN_STATUSES）物理分开；M2 删旧导出时同步从豁免名单移除。
  - Q2：products/ 解散把所有 PA 专属资产（profile/prompt_sections/tools/hooks/skills 物理目录）下沉 src/personal_assistant/，`_product_root()` 扫描退役，属 M1（只排除 reporter/，归 M2）。
  - golden-first 顺序（先补 cron verbatim + 录重构前完整 prompt 快照，再动装配）获认可。

## R1 — cron 段逐字节 golden + 完整 prompt 重构前基线快照

- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression:
  - Visual/Interaction: N/A
- Rollback:
- Commits:
