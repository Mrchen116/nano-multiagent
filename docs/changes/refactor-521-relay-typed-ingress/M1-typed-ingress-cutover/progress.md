# refactor-521-M1 — Progress

## Baseline

- Claim: unit 基线在 typed ingress 改动前全绿。
- Baseline: `milestone/refactor-521-M1` at `a18b88fab666af1862cb6553e38af89c3000b2be`。
- Method: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m 'not e2e' -n 4 --dist worksteal --durations=20 --durations-min=0.5`。
- Result: PASS，`3181 passed, 28 warnings in 238.51s`。
- Locator: 本机 milestone worktree pytest output；warnings 为既有 dependency/deprecation warning。
- Limit: baseline 未运行 e2e/真实 Feishu。

## R1 — 建立 typed carrier 与 producer matrix

- Status: DONE
- Claim: channel callback 现在直接交付带始终存在 `InboundIngress` 的 `InboundMessage`；Web relay/Feishu producer matrix、非法 event-only 组合与 relay required identity 已由最低暴露层测试保护。
- Red: 新 contract 首次 collection 因 `channels.base.ExternalConversationIdentity` 不存在失败；旧 attachment test 随后因继续读取 `inbound.message` 失败，证明 wrapper contract 尚未完全切除。
- Green: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/personal_assistant/test_inbound_ingress.py tests/unit/personal_assistant/test_gateway_web_relay_adapter.py tests/unit/personal_assistant/test_web_relay_adapter_attachments.py tests/unit/test_feishu_adapter.py -q` → `41 passed in 8.67s`；同范围 Ruff → `All checks passed!`。
- Method: deterministic relay payload 与 Feishu provider frame 在真实 adapter callback seam 验证；未 mock typed carrier。
- Commits: `5d158bbd1`。
- Limit: 为保持 roadpoint 可独立回归，下游仍临时附带旧 runtime facts；R2/R3 将切完所有 consumer 后删除该迁移桥与 top-level event identity。

## R2 — 切换 RoutedInbound 与 shadow/session owners

- Status: DONE
- Claim: Gateway pipeline 进入 post-ingress 后只携带 `RoutedInbound`；shadow 状态以 empty/pending/anchored 三态表达，ref-without-saga 被拒绝；session、control、coordinator 与 lifecycle 读取同一 typed authority，typed facts 与 saga 均不写回 message metadata。
- Red: 新状态 contract 首次 collection 因 `GatewayShadowState` 不存在失败；迁移 lifecycle 后旧测试因继续传裸 `InboundMessage`/metadata-derived relay facts 失败，证明 request/lifecycle seam 尚未切换。
- Green: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/personal_assistant/test_routed_inbound.py tests/unit/personal_assistant/test_gateway_shadow_sync.py tests/unit/personal_assistant/test_gateway_im_relay.py tests/unit/personal_assistant/test_inbound_pipeline_session.py tests/unit/personal_assistant/test_inbound_shadow_identity_guard.py tests/unit/personal_assistant/test_session_run_coordinator_admission.py tests/unit/personal_assistant/test_session_run_coordinator_terminal.py tests/unit/personal_assistant/test_session_run_coordinator_steer_identity.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_runtime_delivery_stream.py -q` → `132 passed in 5.48s`。
- Method: 在 pipeline、shadow sync、coordinator admission/terminal、lifecycle callback 与 delivery context 最低公开 seam 上验证三态和分型投影；删除 custom metadata-derived shadow 测试，避免把退役 fallback 固化为 contract。
- Limit: WebRelay producer 的旧 runtime-protocol attachment 与 legacy module 尚保留到 R3 原子删除；全量 persistence/contract/e2e 尚未运行。

## R3 — 投影 runtime delivery 并删除 legacy authority

- Status: TODO

## Promotion Candidates

None.
