# feat-464-M1 — Progress

## Baseline

- Context: 完整读取 spec/design/delta/prototype、AGENTS/SPEC/TESTING_GUIDE/LOGBOOK，并定位现有 IM/Gateway/Feishu/Agent detail seam。
- Evidence:
  - Backend: `71 passed`（account binding、Gateway handler/registry、Feishu adapter/approval）。
  - Frontend: `28 passed`（Agent detail）；现存 React act warning 不影响基线结果。
  - Prototype: 通过真实 Chromium 打开 `prototype.html`，确认四个 M1 must-match 锚点与 out-of-scope provider 约束。

## R1 — IM 安全控制面与 HTTP 入口

- Context: DONE
- Decision: IM channel desired/config、manifest head、status/removal/key 表一次性建齐；所有 channel 命令由按 resolved DB path 创建短连接的 `ChannelControlStore` 用 `BEGIN IMMEDIATE` 串行化。Secret 用 X25519 + HKDF-SHA256 + AES-256-GCM v1 envelope，HTTP 只投影 `secret_configured`。bind confirm 在写 bind/node/profile 之前检查现有 owner，same-user 重放返回同一 confirmed 结果。
- Rationale: app-scoped SQLite handle 仍服务既有 IM repository，但不再承担 channel transaction owner；显式 `credentials.mode` 避免空字符串兼任 keep/replace，App ID 跨 identity 时强制 replace 并清空 app-scoped metadata。
- Evidence:
  - Tests: C1 缺模块按预期 collection red；C2 `18 passed`，覆盖固定 envelope 向量、六维 AAD 篡改、key mismatch、无明文持久化、并发旧 revision 仅一个成功、desired+manifest 原子、HTTP create/list/patch/唯一性/owner 隔离、online/offline cross-owner bind 与 same-owner 重放。
  - Entry: `/im/v1/agents/{agent_id}/channels` GET/POST 与 `/{channel_id}` PATCH 均从 authenticated owner 进入 `ChannelControlService`，错误返回稳定 code；`GET/list` 和日志断言不含 secret。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: account binding contract、multiuser isolation、完整 agent config integration 共 `23 passed`；目标文件 Ruff 通过。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 回滚 R1 三提交会同时移除新增 schema/API/envelope 与 bind guard，不遗留半接线模块；SQLite 仅新增表，无既有数据重写。
- Commits: `31a22fa1c` (C1 red), `4728073f9` (C2 green), C3 为本提交。
- Next: R2 的动态 registry、ChannelManager 与可终止 Feishu worker 红测。

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
