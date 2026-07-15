# feat-464-M3 — Progress

## Baseline

- Context: 完整读取 change-impl-worker、AGENTS/SPEC/COMMENTING_GUIDE/TESTING_GUIDE/LOGBOOK、unit spec/design/delta/prototype 与 M1/M2 tasks/progress/evidence；通过高位 HTTP + headed Chromium 打开 M3 三个 must-match 原型状态，并定位 Feishu client/adapter/worker、ChannelManager/cache/IM connection、ChannelControlStore/GatewayHandler/user stream 与 channels panel seams。
- Evidence:
  - Backend: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/IM/test_agent_channels.py tests/unit/personal_assistant/test_channel_manager.py tests/integration/test_channel_reconcile.py tests/unit/test_feishu_client_scopes.py tests/unit/test_feishu_adapter_scope_warning.py` → `18 passed`。
  - Frontend: `npm run test -- agent-channels-panel.test.tsx agent-status-ws-consumer.test.ts im-agent-config-api.test.ts` → `3 files / 21 passed`；`npm run build` → PASS（443 modules transformed）。
  - Prototype: `http://127.0.0.1:59609/.../prototype.html` headed Chromium 验证 `#channel-limited` 同时含 confirmed missing + unknown、`#channels-error` error/retry 且无 empty、移动模式单列及 add bottom sheet；唯一 console error 是 prototype 既有 `/favicon.ico` 404，server/browser 已清理。
- Next: R1 先提交 capability catalog/tenant grant/structured diagnostics 红测，再实现生产路径。

## R1 — Feishu 租户授权目录与结构化诊断

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
- Next: R2

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
