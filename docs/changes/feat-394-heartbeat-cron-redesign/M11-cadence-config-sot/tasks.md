# feat-394-M11 cadence-config-sot — Tasks

## 目标

修 bug A（PR #78 验收暴露）：scheduler 顶层节律改读 `agent.heartbeat_every`（config，默认 30m），
退役 HEARTBEAT.md 顶层 `every:` 解析；UI cadence 绑 config 真值（删硬编码 30m 兜底）；
heartbeat 特性下加可折叠 HEARTBEAT.md 只读预览（仿 promptPreview 那套）。

## 退出标准

- `[worker]` scheduler 顶层节律取 `config.heartbeat_every`（默认 30m）、忽略 md 顶层 `every:` 的单测
- `[worker]` `tasks:` per-task 子节律仍读 md、不受影响 的单测
- `[worker]` 前端删硬编码 30m 兜底、cadence 绑后端值 的 vitest
- `[worker]` `pytest -m "not e2e"` 全绿（含 im_service）+ tsc -b + vitest 绿

## 测试策略

- R1（后端）：单测驱动，红→绿；测 scheduler 读 config.every 而非 md every，测 tasks: 子节律不受影响
- R2（前端）：vitest 驱动 + 浏览器验收；测删硬编码兜底、cadence 绑后端值、HEARTBEAT.md 只读预览

### 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| scheduler 读 config.every 而非 md every | 单测 | 是 |
| md 顶层 every: 被忽略 | 单测 | 是 |
| tasks: per-task 子节律不受影响 | 单测 | 是 |
| 前端删硬编码 30m 兜底 | vitest | 是 |
| HEARTBEAT.md 只读预览折叠展示 | 浏览器验收 + vitest | 是（vitest）|

### UI 状态矩阵

- default（heartbeat 开启，every=30m）: cadence 显示 30m，展开预览显示 HEARTBEAT.md 内容
- heartbeat 未配置 every: 显示默认 30m（来自后端，非硬编码）
- HEARTBEAT.md 不存在: 预览显示空/提示文字
- loading 中: 预览 loading 状态
- 浏览器宽度 1440px

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 后端：scheduler 读 config.every，退役 md 顶层 every | TODO |
| R2 | 前端：删硬编码兜底 + HEARTBEAT.md 只读预览 | TODO |
