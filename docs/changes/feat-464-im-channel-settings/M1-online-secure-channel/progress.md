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

- Context: DONE
- Decision: `ChannelManager` 成为 managed external channel 的单一 lifecycle owner；runtime identity 只由 provider + agent 派生为 `feishu:<agent_id>`。App identity/generation 同时约束 metadata 与 status；owner/bot metadata 采用 set-if-null first-wins。Feishu SDK listener 从 Gateway 线程迁入每 Bot 一个 spawn process，parent 保留 REST、adapter、approval 与 kernel callback。
- Rationale: `ChannelRegistry` 只提供锁保护的 register/replace/remove，不吸收调和规则；worker 用 message FIFO、latest status mailbox、priority pipe、card-action duplex pipe 四类职责明确的 IPC，并以 incarnation + sequence 在 parent 单点归并。
- Evidence:
  - Tests: C1 两个新模块 collection red；C2 `40 passed` 覆盖稳定 runtime name、stop-before-start cutover、旧 generation 双拒绝、App replacement metadata 清空/owner 重绑、feishu-doc activation、双 listener 进程隔离、真实 stop/join、FIFO backpressure、status coalescing、priority error、drain/drop、card correlation/timeout、worker crash，以及既有 approval first-wins。
  - Entry: `FeishuClient.start()` 只在 parent 创建 REST client，SDK `WSClient` 与 event loop 在 `FeishuWorkerRuntime` child process；`FeishuAdapter.stop_invalidated()` 为 replace/disable/delete 立即丢弃旧 generation 输入。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 全部既有 Feishu adapter/client/history/mention/send 关联测试 `61 passed`；目标文件 Ruff 通过；测试退出后无残留 worker process。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 回滚 R2 三提交恢复静态 registry + daemon thread；不会影响 R1 IM schema/API，但动态 manifest 不能再热应用。
- Commits: `054e4810f` (C1 red), `3577ad112` (C2 green), C3 为本提交。
- Next: R3 把 node key、manifest reconcile、status/metadata result 接入现有单槽 IM WebSocket FIFO 和 Gateway composition root。

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
