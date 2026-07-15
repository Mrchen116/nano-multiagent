# feat-464-M1 — Progress

## Baseline

- Context: 完整读取 spec/design/delta/prototype、AGENTS/SPEC/TESTING_GUIDE/LOGBOOK，并定位现有 IM/Gateway/Feishu/Agent detail seam。
- Evidence:
  - Backend: `71 passed`（account binding、Gateway handler/registry、Feishu adapter/approval）。
  - Frontend: `28 passed`（Agent detail）；现存 React act warning 不影响基线结果。
  - Prototype: 通过真实 Chromium 打开 `prototype.html`，确认四个 M1 must-match 锚点与 out-of-scope provider 约束。

## R1 — IM 安全控制面与 HTTP 入口

- Context: DOING
- Decision: 待完成。
- Rationale: 待完成。
- Evidence:
  - Tests: 待完成。
  - Entry: 待完成。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 待完成。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 待完成。
- Commits: 待完成。
- Next: C1 红测。

## R2 — Gateway 动态 runtime 与 Feishu worker

- Context: TODO
- Next: R1 完成后开始。

## R3 — WS 在线 reconcile/status 闭环

- Context: TODO
- Next: R2 完成后开始。

## R4 — Agent 通道页与 provider registry

- Context: TODO
- Next: R3 完成后开始。

## R5 — 真栈/真浏览器证据与总门禁

- Context: TODO
- Next: R4 完成后开始。

## Prototype Comparison

| Reference | Required contract | Actual evidence | Viewport / state | Result | Deviation rationale |
|---|---|---|---|---|---|
| `#channels-empty` | 通用空态 + 添加入口；无 Web IM | 待补 | desktop / empty | blocked | 尚未实现 |
| `#add-feishu` | provider 禁选、required、keep/replace | 待补 | desktop / modal | blocked | 尚未实现 |
| `#channel-connecting` | 在线保存后的 connecting | 待补 | desktop / connecting | blocked | 尚未实现 |
| `#channel-connected` | 当前配置已应用 + 最近状态时间；无 revision | 待补 | desktop / connected | blocked | 尚未实现 |
