# bugfix-446-M1 — Progress

> 单 M1。三提交循环 C1 红测 / C2 实现 / C3 文档，逐 roadpoint 推进。

## 启动澄清记录

- 范围理解无歧义，已向 orchestrator 报信「已读懂」。
- §0.13 决定：design Milestone 范围列含 `docs/specs/gateway/spec.md`（收尾归并 delta），但契约层
  canonical 归 orchestrator，delta-spec 自身也写明「收尾由 orchestrator 并入 canonical」。故本
  milestone 不写 `docs/specs/gateway/spec.md`，只保留 design-author 已写的
  `docs/changes/bugfix-446-gateway-im-resilience/specs/gateway/spec.md`。已知会 orchestrator。

## R1 — 连接层异常边界 + 首连落定信号 + InvalidStateError 防御

- Context: `run_forever` 的 `except Exception` 漏 `CancelledError`（BaseException），cancel 时跳过
  `_mark_disconnected` 清理（issue 路径 5）。移除 eager connect（R2）后还需一个「首次连接尝试落定」
  信号让心跳启动等握手（决策 3 配套护栏，防 feat-393 回退）。`set_exception` 理论 TOCTOU（决策 6）。
- Decision:
  - `run_forever` except 拆三路：`CancelledError`→`_mark_disconnected()` 清理后 `raise`；`Exception`→
    `_mark_disconnected(exc)` + 退避重试；其余 `BaseException` 不接，漏给外层 watchdog（R2）。
  - 新增 lazy `asyncio.Event` `_first_connect_resolved` + `_first_attempt_event()` + `wait_first_connect_attempt(timeout=)`；
    首次 connect resolve（成功或失败）即 `set()`，wait 带超时上限兜底（防 connect 挂死）。
  - `_mark_disconnected` 的 `set_exception` 包 `contextlib.suppress(asyncio.InvalidStateError)`。
- Rationale: cancel 必须先清理再尊重取消语义；普通异常是瞬态退避重试；进程级信号不强吞（强吞会破坏
  shutdown）。首连信号只 gate 首 tick、不改 local-autonomy（IM 不可达时首尝试失败也 set，心跳照常起步）。
  Event lazy 创建以绑定真正运行 run_forever / waiter 的事件循环。
- Evidence:
  - Tests: `pytest tests/unit/personal_assistant/test_gateway_im_resilience.py test_gateway_im_connection_behavior.py test_gateway_connect_once.py` → 27 passed。
    新增 5 红测：cancel 清理+re-raise / 首连成功 set / 首连失败 set / wait 超时有界 / InvalidStateError 不外泄。
  - Entry: N/A（连接层纯逻辑；真栈入口验证在 R4 e2e）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 连接层回归（既有 22 例）全绿；真栈 e2e 在 R4。
  - Visual/Interaction: N/A
  - Lint: `ruff check` + `ruff format --check` 两文件通过。
- Rollback: 回退到 C1 commit abd55a02（红测在、实现未上）。
- Commits: C1=abd55a02, C2=8a138850, C3=(本提交)
- Next: R2 — main.py GatewayRuntime watchdog + 移除 eager connect + 心跳首连门 + finally 硬化。
