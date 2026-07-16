# M7 — Progress

实现基线：`fb8308ae8ca6fb980fb748b9fb74140385edb8b5`。Baseline focused backend `37 passed`；focused frontend `13 passed`。

## Scope decision — 旧配置迁移移出 M7

- 用户明确不考虑旧 `config.yaml` 或历史 backup 的后向兼容、自动迁移与清理；原 M7 item 4 已停止且未产生代码/测试改动。
- 本 milestone 的安全边界仅验证 IM 通道页新建/更新不会向 `config.yaml` 写入 App Secret；既有旧配置与历史 backup 为 out-of-scope。

## R1 — Status wire owner 与 coalescing race

- Context: TODO。
- Decision: TODO。
- Rationale: TODO。
- Evidence:
  - Tests: TODO。
  - Entry: TODO。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: TODO。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: TODO。
- Commits: TODO。

## R2 — 断线 incarnation supersede 与 control correlation

- Context: TODO。
- Decision: TODO。
- Rationale: TODO。
- Evidence:
  - Tests: TODO。
  - Entry: TODO。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: TODO。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: TODO。
- Commits: TODO。

## R3 — Removal 自动成功清理旧反馈

- Context: TODO。
- Decision: TODO。
- Rationale: TODO。
- Evidence:
  - Tests: TODO。
  - Entry: TODO。
  - Frontend State Matrix: error、waiting、empty、missing resource。
  - Browser QA: 延至 R4。
  - E2E/Regression: TODO。
  - Visual/Interaction: 延至 R4。
  - Prototype Comparison: 延至 R4。
- Rollback: TODO。
- Commits: TODO。

## R4 — Targeted browser 与一次性全量门禁

- Context: TODO。
- Decision: TODO。
- Rationale: TODO。
- Evidence:
  - Tests: TODO。
  - Entry: TODO。
  - Frontend State Matrix: TODO。
  - Browser QA: TODO。
  - E2E/Regression: TODO。
  - Visual/Interaction: TODO。
  - Prototype Comparison: TODO。
- Rollback: TODO。
- Commits: TODO。

Prototype Comparison：
| Reference | Required contract | Actual evidence | Viewport / state | Result | Deviation rationale |
|---|---|---|---|---|---|
| `prototype.html#channel-deleting` | retry error/waiting 只随 receipt 存在 | TODO | desktop / failed→empty | blocked | 等待 R4 |
| `prototype.html#channels-empty` | 收敛后只显示空态，无旧 alert/notice | TODO | desktop / empty | blocked | 等待 R4 |
