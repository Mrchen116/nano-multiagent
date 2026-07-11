# refactor-459-M2 — Progress

## 基线

- Context: M2 开始前确认 node/register/status/offline 与 M1 seam contract 的现有行为可用。
- Evidence: `pytest -q tests/contract/test_im_persistence_seam_contract.py tests/im_service/unit/test_gateway_handler.py tests/im_service/unit/test_gateway_status_broadcast.py tests/im_service/unit/test_offline_guard.py tests/im_service/unit/test_nodes_metrics_repositories.py tests/im_service/integration/test_gateway_im_registration.py tests/im_service/integration/test_gateway_websocket_api.py` → `76 passed`。

## R1 — GatewayNodePersistence interface 与 durable failure compatibility

- 状态：DOING
- Next: 先提交真实 SQLite interface/failure-injection 红测，再实现 concrete module；逐表记录重构前与重构后 durable rows。

## R2 — Gateway handler node lifecycle 接线与广播不变

- 状态：TODO

## R3 — Timeout scan 与 seam contract 收口

- 状态：TODO
