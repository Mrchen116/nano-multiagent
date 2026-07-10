# refactor-454-M3: fix-runtime-lifecycle-owner — Tasks

> 对齐: ../design.md Changelog 2026-07-07 post-acceptance round 1

## 目标

修复 round-1 verifier/code-review 发现的 M2 残留问题：relay lifecycle 的 accepted/running/completed/failed/cancelled delivery 语义由 `personal_assistant.gateway.runtime_delivery.lifecycle` 承接，`main.py` 只负责 wiring；production typed `RunDeliveryContextStore` fresh accepted relay 仍必须发送 `node.delivery_receipt(delivery_status="sent")`，不能因 typed seed 成功提前返回。

## 退出标准

- [x] `main.py` 不再定义 `_build_relay_lifecycle_callback()`，只 import/wire runtime delivery lifecycle builder。
- [x] `runtime_delivery.lifecycle` owns relay accepted/completed/failed/cancelled、RunDeliveryContext seed/pop、delivery receipt/report、Feishu processing-start ack。
- [x] typed `RunDeliveryContextStore` fresh accepted relay 会发送 `node.delivery_receipt(delivery_status="sent")` 并保留 accepted progress。
- [x] observer/lifecycle 不在入口无条件把 typed store 降级为 `legacy_contexts`；legacy dict 只保留在 heartbeat/cron 等明确 legacy boundary。
- [x] 既有 running/completed/failed/cancelled report/cleanup 行为不回退。
- [x] 指定门禁全绿：
  `pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py tests/contract/test_personal_assistant_main_contract.py`
- [x] worktree-local live isolated check 验证 Web IM direct relay 可见 reply，以及 relay accepted/completed 状态 closeout；Feishu/Lark 真平台凭据若仍缺失，只记录 caveat，不用 fake inbound 顶替。

## 测试策略

- 被测行为（来自退出标准）：
  - typed `RunDeliveryContextStore` 的 fresh relay accepted path 同时 seed context 和发送 `delivery_status=sent` receipt。
  - `main.py` 只 wiring runtime delivery lifecycle builder，不定义 relay lifecycle delivery owner。
  - running/completed/failed/cancelled 继续发送 report/receipt 并清理 context。
  - observer/lifecycle 不在 builder 入口把 typed store 无条件替换成裸 `legacy_contexts`。
- 已有测试在：
  - `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`（扩展），覆盖 accepted receipt 红测、lifecycle owner、cleanup/report 回归。
  - `tests/contract/test_personal_assistant_main_contract.py`（扩展），覆盖 `main.py` 不再定义 `_build_relay_lifecycle_callback`。
  - 如 observer 调整影响 typed-store boundary，在同一 lifecycle unit 文件中扩展覆盖，不新建文件。
- 落层/目录/marker：`tests/unit/`、`tests/contract/`，marker：无。live isolated check 作为一次性验收证据写入 `progress.md`，不进测试套件。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：worktree `.e2e-ports.env`、`.im.log`、`.gateway.log` 中的状态核对摘要；临时服务由 `scripts/e2e-down.sh` 清理。

前端 UI：N/A。本 milestone 不改前端客户端面；Web IM live 路径通过同一 HTTP/WS 后端入口和 API/DB 状态核对验证用户可见结果。

## Roadpoints

### R1 — Red regressions for lifecycle owner and typed accepted receipt

- 状态: DONE
- 步骤:
  - 在 relay lifecycle unit tests 中新增 typed store fresh accepted relay receipt 红测。
  - 在 main contract 中新增 `main.py` 不定义 `_build_relay_lifecycle_callback` 的架构红测。
  - 必要时新增 observer typed-store boundary 红测。
- 验证:
  - `pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/contract/test_personal_assistant_main_contract.py` 预期失败在新增断言。

### R2 — Move lifecycle owner to runtime_delivery and fix typed-store receipt

- 状态: DONE
- 步骤:
  - 新增 `src/personal_assistant/gateway/runtime_delivery/lifecycle.py`，迁入 relay lifecycle builder、protocol conversation id、external processing-start ack。
  - `main.py` 仅 import/wire builder，删除 lifecycle delivery helper 定义和不再需要的 imports。
  - 修复 typed store accepted path：seed typed context 后继续执行 relay receipt/report 分支，不提前 return。
  - 调整 observer/context helper，避免在入口无条件把 typed store 替换为 legacy dict。
- 验证:
  - 指定窄门禁全绿，必要时跑 `ruff check` 覆盖 touched files。

### R3 — Evidence and live isolated check

- 状态: DONE
- 步骤:
  - 记录 R1/R2 测试证据和 rollback commits。
  - 用 worktree-local e2e stack 验证 Web IM direct relay 可见 reply、relay accepted/completed 状态 closeout。
  - 如 Feishu/Lark 凭据仍缺失，明确 caveat。
- 验证:
  - 指定完整门禁全绿。
  - live isolated check 有可复查命令/状态摘要。
