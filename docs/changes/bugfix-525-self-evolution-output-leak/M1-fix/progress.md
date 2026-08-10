# bugfix-525-M1 — Progress

## 启动基线

- Unit head at dispatch: `57b7aec1d`。
- Scope confirmation: 只隔离 self-evolution fork 的 raw session events；普通 background Agent result 与既有 `self_evolution_review` 展示路径保持不变。
- Existing baseline: `51 passed`，命令见 R2 完成记录。
- Production evidence read-only locators:
  - Kernel session: `sess_5f9eeb9f7479dd13`
  - LLM request/tool call: `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-09_20-27-23_509_sess_5f9eeb9f7479dd13/2026-08-10_09-41-03_357-req-anthropic_messages.json`
  - LLM raw completion: `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-09_20-27-23_509_sess_5f9eeb9f7479dd13/2026-08-10_09-41-09_400-non-stream-res-anthropic_messages.json`
  - User-visible screenshot: `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-ea146fbc-d9d7-41d9-aded-947376fc38e4.png`

## R1 — 真实 fork session-event 红测与隔离修复

- Status: TODO
- Next: 写 integration regression 并确认红测只因 side-chain raw event 泄漏失败。

## R2 — 继承不变量与既有测试维护

- Status: TODO

## R3 — 比例门禁与 Bugfix lite 证据闭环

- Status: TODO

## Promotion Candidates

None.
