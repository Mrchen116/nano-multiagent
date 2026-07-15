# feat-464-M3 — Progress

## Baseline

- Context: 完整读取 change-impl-worker、AGENTS/SPEC/COMMENTING_GUIDE/TESTING_GUIDE/LOGBOOK、unit spec/design/delta/prototype 与 M1/M2 tasks/progress/evidence；通过高位 HTTP + headed Chromium 打开 M3 三个 must-match 原型状态，并定位 Feishu client/adapter/worker、ChannelManager/cache/IM connection、ChannelControlStore/GatewayHandler/user stream 与 channels panel seams。
- Evidence:
  - Backend: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/IM/test_agent_channels.py tests/unit/personal_assistant/test_channel_manager.py tests/integration/test_channel_reconcile.py tests/unit/test_feishu_client_scopes.py tests/unit/test_feishu_adapter_scope_warning.py` → `18 passed`。
  - Frontend: `npm run test -- agent-channels-panel.test.tsx agent-status-ws-consumer.test.ts im-agent-config-api.test.ts` → `3 files / 21 passed`；`npm run build` → PASS（443 modules transformed）。
  - Prototype: `http://127.0.0.1:59609/.../prototype.html` headed Chromium 验证 `#channel-limited` 同时含 confirmed missing + unknown、`#channels-error` error/retry 且无 empty、移动模式单列及 add bottom sheet；唯一 console error 是 prototype 既有 `/favicon.ico` 404，server/browser 已清理。
- Next: R1 先提交 capability catalog/tenant grant/structured diagnostics 红测，再实现生产路径。

## R1 — Feishu 租户授权目录与结构化诊断

- Context: M1 只用 `scope_name` 存在性发启动 warning，既不读取 `grant_status/scope_type`，也没有能进入 IM/UI 的结构化 capability catalog；因此 grant=2 和 user identity 会被误报为应用权限完整。
- Decision: 新增 provider-owned immutable catalog，逐项声明 current/legacy `accepted_scope_sets` 与只含 current scopes 的 `recommended_scopes`；`FeishuClient` 在启动 worker 前只调用一次 application v6 tenant authorization status，把完整 probe 归一为 granted set，缺字段/未知枚举/API/解析失败整次 unknown。每个 worker connection status 都附带 aggregate + checks，经 `ChannelManager` 与 production status bridge 进入 IM 协议。
- Rationale: scope 归一、等价集合与诊断汇总集中在 provider 深模块，adapter 不再重复调用单 scope warning 路径；连接状态仍由 worker incarnation/sequence 负责，诊断只作为正交字段附着，因此 permission unknown 不会变成 connection failed。
- Evidence:
  - Tests: C1 缺 `feishu.diagnostics` 按预期 collection red；C2 provider/client/manager/worker 组合 `79 passed`，production runtime/reconcile/shutdown 接线 `16 passed`，test naming/size contract `2 passed`。
  - Entry: `FeishuClient.start()` 构造真实 SDK REST client 后先读取一次 `/application/v6/scope/list` 语义，再启动 listener；`main._send_channel_status()` 把每项 `check_id/state/accepted_scope_sets/recommended_scopes/effect/remediation` 发入真实 `channel.status` frame。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 逐个参数化证明 p2p/group-at/send/group-message/history/group-history/reaction/chat 的每个 current/legacy accepted set 都能 satisfied；grant=2、user identity 不进入 granted set，缺 status/type、未知 enum、API/parse failure 均 unknown；普通群 history 只在完整 history + group-message set 时满足。
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: 回滚 R1 C2 恢复旧启动 warning，不改变 M1/M2 lifecycle schema；R1 C1 同时回滚以恢复旧测试契约。
- Commits: C1=`cf2370368`，C2=`5d08c5c7f`，C3=本提交。
- Next: R2 为 incarnation barrier/latest snapshot 建立 durable outbox，并让 terminal stale/removed ACK 在释放 FIFO 后执行 drop/quarantine；同时补 IM user-stream 精确失效。

## R2 — 状态因果、terminal ACK 与 user-stream 精确刷新

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: TODO
- Commits: TODO
- Next: R3

## R3 — limited/unknown/error 与移动端 sheet

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: TODO
  - Browser QA: TODO
  - E2E/Regression: TODO
  - Visual/Interaction: TODO
  - Prototype Comparison: TODO
- Rollback: TODO
- Commits: TODO
- Next: R4

## R4 — 真栈浏览器、真实飞书 smoke 与总门禁

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: TODO
  - Browser QA: TODO
  - E2E/Regression: TODO
  - Visual/Interaction: TODO
  - Prototype Comparison: TODO
- Rollback: TODO
- Commits: TODO
- Next: 完成 M3 并集成 unit branch

## Prototype Comparison

| Reference | Required contract | Actual evidence | Viewport / state | Result | Deviation rationale |
|---|---|---|---|---|---|
| `#channel-limited` | limited + unknown checks；raw scope、影响、修复；普通群背景上下文 | TODO | desktop / limited + unknown | blocked | 待 R4 真入口证据 |
| `#channels-error` | list error + retry；不渲染空态 | TODO | desktop / error | blocked | 待 R4 真入口证据 |
| `#channels-mobile` | 375×812 单列卡片 + bottom sheet，动作可触达 | TODO | 375×812 / connected+limited+sheet | blocked | 待 R4 真入口证据 |
| `#channel-reconnecting/#channel-failed` | 连接故障与权限 unknown 分层 | TODO | desktop/mobile / reconnecting + unknown | blocked | 待 R4 真入口证据 |
