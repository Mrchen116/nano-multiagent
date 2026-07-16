# M8 — Delivery terminal outcome 与 unattended capability 收口

## Goal

修复 Round 3 暴露的三处所有权断点：共享 stream helper 必须返回 canonical terminal outcome；cron 按真实 terminal status 持久化且失败/取消不写成功 awareness；shadow sync 复用 typed-first identity；cron/heartbeat unattended session 继承 agent 的非空受限 skills。

## Exit criteria

- [ ] stream helper 仅以 `agent.sdk.TERMINAL_RUN_STATUSES` 判定终态，并返回 status、partial/final text、context 与 error。
- [ ] failed/cancelled cron 保留真实历史状态，不写成功 awareness；缺失 terminal event 时可终止为失败而不挂起。
- [ ] shadow sync 支持 typed-only external identity、拒绝 IM-origin identity，并保留 legacy metadata fallback。
- [ ] cron 与 heartbeat 创建 unattended session 时透传非空 `agent.config.skills`；空配置继续兼容为 `None`。
- [ ] 聚焦回归、ruff 与 `pytest -m "not e2e"` 全部通过。
- [ ] milestone 分支合入并推送 `unit/refactor-463`，随后清理 milestone worktree/branch。

## Test strategy

- `tests/unit/personal_assistant/test_runtime_delivery_stream.py`: canonical failed/cancelled terminal、partial text、无 terminal 快速失败。
- `tests/unit/personal_assistant/test_cron_execution_owner_chain.py`: cron completed/failed/cancelled 的 history 与 awareness 分流。
- `tests/unit/personal_assistant/test_gateway_shadow_sync.py`: typed-only external、IM-origin guard、legacy fallback。
- `tests/unit/personal_assistant/test_unattended_session_skills.py`: cron/heartbeat restricted skills 与 empty/None 兼容。
- 非前端改动，无 frontend build/test 要求。

## Roadpoints

### R1 — Stream terminal outcome 与 cron 状态闭环 (DONE)

- [x] C1 红测：锁定 canonical terminal vocabulary、partial text、no-terminal 与失败 awareness 行为。
- [x] C2 实现：typed stream outcome；cron 按 outcome 持久化。
- [x] C3 文档：记录行为、测试与验证证据。

### R2 — Shadow sync typed-first identity (DONE)

- [x] C1 红测：typed-only external、IM-origin guard、legacy fallback。
- [x] C2 实现：复用 canonical identity extractor 并清理 runtime metadata。
- [x] C3 文档：记录行为、测试与验证证据。

### R3 — Unattended skills 继承 (DOING)

- [ ] C1 红测：cron/heartbeat restricted 与 empty compatibility。
- [ ] C2 实现：`_KernelClientShim` 透传非空 restricted skills。
- [ ] C3 文档：记录行为、测试与验证证据。
