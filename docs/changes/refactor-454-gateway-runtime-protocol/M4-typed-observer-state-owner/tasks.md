# refactor-454-M4: typed-observer-state-owner — Tasks

> 对齐: ../design.md Changelog 2026-07-07 post-verification round 2

## 目标

关闭 verifier round-2 blocker：`RunDeliveryContextStore` 必须成为 observer / `roll_bubble()` 的 primary runtime state surface。observer 不再在 builder entry 把 typed store 投影成 `legacy_contexts` 后全程读写；运行态 backfill（`message_id`、resolved `conversation_id`、`kernel_message_id`、rolling、external current text / marker、permission/external metadata）必须回写 typed store。用户侧 frame shape、文案、入口、配置流程保持不变。

## 退出标准

- [ ] `RunDeliveryContextStore` 暴露 typed read/update/backfill API，覆盖 observer 当前会读写的运行态字段。
- [ ] `build_kernel_event_observer()` typed-store path 直接通过 store API 读写状态；legacy dict 只作为兼容边界，不是 observer 主状态。
- [ ] `roll_bubble()` 接收 typed store 时更新 typed store 的 `message_id` / `kernel_message_id` / rolling state。
- [ ] typed relay/shadow path：`run_status=running` + IM ack 后，typed context/store 自身持有 backfilled `message_id`。
- [ ] typed owner-direct/lazy path：assistant content 触发 `turn_start` 后，typed context/store 自身回填 resolved `conversation_id` 和 `message_id`，并继续发送 delta。
- [ ] 保留 legacy dict path 兼容测试，heartbeat/cron 明确 legacy boundary 和现有测试不回退。
- [ ] 指定 touched-file `ruff check` 全绿。
- [ ] 指定 M4/M3 gate 全绿：
  `pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py tests/contract/test_personal_assistant_main_contract.py`
- [ ] 如改动超出 `context.py` / `observer.py` / `lifecycle.py` / 相关 tests，复跑 `pytest -m "not e2e"`。
- [ ] Feishu/Lark 真平台缺凭据时只记录 caveat，不用 fake inbound 顶替。

## 测试策略

- 被测行为（来自退出标准）：
  - typed `RunDeliveryContextStore` seed 后，observer `run_status=running` ack backfill 写回 typed store 自身，而非只写 `legacy_contexts`。
  - typed owner-direct context 的 lazy `turn_start` ack backfill 写回 typed store 自身，并继续发送 `message_delta`。
  - `roll_bubble()` typed-store path 更新 typed store 的 `message_id`、`kernel_message_id` 和 rolling state。
  - legacy dict path 仍兼容现有 observer / heartbeat / cron 测试。
- 已有测试在：
  - `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`（扩展），覆盖 typed store shadow/owner-direct/roll_bubble 行为回归。
  - `tests/unit/personal_assistant/test_heartbeat_im_delivery.py`（必要时调整），覆盖 owner-direct typed store 断言从 legacy projection 转向 typed state。
  - `tests/unit/personal_assistant/test_steer_bubble_roll.py`、`tests/unit/personal_assistant/test_relay_kernel_message_id.py` 保留 legacy dict path，不新建文件。
- 落层/目录/marker：`tests/unit/`，marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无；本轮为后端 observer state owner 修复，真实入口使用既有 unit/integration gate 和 M3 live evidence，Feishu/Lark caveat 记录在 progress。

前端 UI：N/A。本 milestone 不改前端客户端面、frame shape 或可见文案。

## Roadpoints

### R1 — Red regressions for typed observer state ownership

- 状态: TODO
- 步骤:
  - 扩展现有 observer/lifecycle 测试，断言 typed store 自身（不是 `legacy_contexts`）在 shadow ack、owner-direct ack、`roll_bubble()` 后持有运行态 backfill。
  - 运行新增/相关测试，确认当前实现失败。
- 验证:
  - `pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_steer_bubble_roll.py tests/unit/personal_assistant/test_relay_kernel_message_id.py` 预期失败在新增 typed-store owner 断言。

### R2 — Make typed store the observer state surface

- 状态: TODO
- 步骤:
  - 扩展 `RunDeliveryContext`/`RunDeliveryContextStore`，新增 runtime state view 和 typed update/backfill API。
  - 调整 observer / `roll_bubble()` typed-store 分支，运行态读写通过 store API；legacy dict 使用窄 adapter。
  - 必要时调整 lifecycle seed/discard，保持 legacy projection 兼容。
- 验证:
  - touched-file `ruff check` 全绿。
  - R1 新增回归及 legacy observer 相关测试全绿。

### R3 — Gate, documentation, integration evidence

- 状态: TODO
- 步骤:
  - 跑完整 M4/M3 gate。
  - 若 touched scope 超出计划，跑 `pytest -m "not e2e"`。
  - 更新 `progress.md`，记录红测、实现、验证和 Feishu/Lark caveat。
- 验证:
  - 指定 gate 全绿。
  - progress 记录 commit hashes、rollback 和 caveat。
