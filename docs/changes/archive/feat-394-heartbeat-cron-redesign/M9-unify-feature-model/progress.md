# feat-394-M9 Progress

## Baseline

`pytest -m "not e2e"`: 2483 passed, 2 failed（macOS /tmp vs /private/tmp path flaky，
与 M9 无关，设计文档已记录 feat-393 macOS 预存失败）。
rebase to origin/unit/feat-394: 成功。

---

## R1 — FEATURE_REGISTRY 加 cron_scheduling + heartbeat 条目

C1(test): `test(feat-394/M9/R1)` 红测通过后新增实现。
C2(impl): `feat(feat-394/M9/R1)` FEATURE_REGISTRY 加 product-layer 两条目。

## R2 — prompt gates 迁移 ctx.vars → ctx.flags

C1(test): `test(feat-394/M9/R2)` 红测 heartbeat/cron gate 仍读 ctx.vars。
C2(impl): `feat(feat-394/M9/R2)` gate 改读 ctx.flags["heartbeat"]/["cron_scheduling"]。

## R3 — AgentWorkspaceConfig @property

C1(test): `test(feat-394/M9/R3)` 红测。
C2(impl): `feat(feat-394/M9/R3)` heartbeat_enabled/cron_enabled → @property from features。

## R4 — inbound_pipeline cleanup

C1(test): `test(feat-394/M9/R4)` 红测。
C2(impl): `feat(feat-394/M9/R4)` 移除 cron_enabled 参数 + standalone metadata keys。
已清除 im_service/integration 多个快照的残留字段。

## R5 — upstream_reporter + IM backend

C1(test): `test(feat-394/M9/R5)` 红测 tools → {name,description,default_on}。
C2(impl): `feat(feat-394/M9/R5)` _build_tool_names 改返回 dict 元组 + IM routes 双写 features。

## R6 — Frontend

C2(impl): `feat(feat-394/M9/R6)` frontend —
- PillSelector: default_on + useDefaultOn（空 allowlist 显示默认选中）
- im-agent-config-api: 传递 default_on
- agent-detail-page: HeartbeatCard/CronCard 条件渲染，hideEnableToggle prop
- onFeatureToggle 同步写 draft.heartbeat/cron.enabled
- i18n: heartbeat/cron_scheduling 文案

## R7 — 全树绿

`pytest -m "not e2e"`: 2535 passed, 2 failed（macOS /tmp 预存问题，与 M9 无关）。
`tsc -b --noEmit`: 通过。
`vitest run`: 361 passed, 0 failed。
`ruff check + ruff format --check`: 通过。

修复 2 个 M9 引入的测试回归：
- test_prompt_sections_golden: flags={} 时 heartbeat section 不应出现（改 present→absent）。
- test_preview_heartbeat_cron_params: mock 需设 profile.features（M9 fallback 路径已改）。
