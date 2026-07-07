# refactor-454-M2: runtime-delivery — Tasks

> 对齐: ../design.md v1

## 目标

把 Gateway run context、relay lifecycle、kernel runtime event delivery、background/control visible replies 和 session-event IM notification 从 `main.py` 收口到 `personal_assistant.gateway.runtime_delivery`，保持 Web IM、Feishu/shadow、running/tool/permission、heartbeat/cron owner-direct 和 Gateway/IM 重连用户可见行为不变。

## 退出标准

- [x] 非 Feishu 真平台部分通过自动化/真栈回归；Feishu-specific 私聊/群聊/未 @ 群消息 shadow/IM 离线主路径因本隔离栈无真实 Feishu/Lark 凭证标记为未验，不伪造 inbound。
- [x] Gateway/IM 瞬断和 Gateway 重启后节点/会话恢复语义不变。
- [x] heartbeat/cron owner-direct 可自动验证部分已覆盖：cron 真栈有内容推送通过；heartbeat 主动冒泡真栈维持既有 XFAIL #126；`NO_REPLY` / `HEARTBEAT_OK` 静默和 ack 回填由单测覆盖。
- [x] `main.py` 不再直接持有裸 `_run_context_store`、kernel event delivery 大分支、background/control 可见回复和 session-event IM notification 语义，composition root 只 wiring。
- [x] `RunDeliveryTarget` 显式覆盖 `shadow`、`owner_direct`、`none`，且 owner direct 不复用 `ShadowConversationRef`。
- [x] lifecycle cleanup 覆盖 accepted/completed/failed/cancelled/tool/permission/background/heartbeat/cron。
- [x] owner lazy-direct 单测覆盖：首个真实 content 前不发 `turn_start`，`NO_REPLY` / `HEARTBEAT_OK` 静默，ack 后回填 `conversation_id/message_id` 并继续 delta。
- [x] 指定门禁测试全绿：
  `pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py`
- [x] unit 集成分支最终跑 `pytest -m "not e2e"`。
- [x] live-critical 真栈证据记录：Web IM trigger -> running/final 可见、Gateway/IM 重启/重连、cron owner-direct 有内容冒泡通过；heartbeat 主动冒泡为既有 XFAIL #126；Feishu-specific 旅程缺真实 Feishu/Lark 凭证，明确标记未验。

## 测试策略

- 被测行为（来自退出标准）：
  - Run delivery context 用 typed target 表达 shadow / owner-direct / none，accepted seed 不复用裸 dict 语义，completed/failed/cancelled/reconcile/heartbeat/cron 后 cleanup。
  - relay lifecycle 继续发送 delivery receipt/report、Feishu started ack，并从 M1 typed runtime protocol facts 读取 shadow/external/relay 字段。
  - kernel event observer 继续保持 running placeholder、message delta/completed、tool start/end/reconcile、permission request/resolved、external visible mirror、owner lazy-direct 静默/冒泡/ack 回填行为。
  - background/control visible replies 和 `self_evolution_review` session event notification 继续投递到正确的 external/shadow/IM conversation。
  - IM connection resilience 和 Gateway websocket API 语义不因 wiring 抽取漂移。
- 已有测试在：
  - `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`（扩展），覆盖 typed delivery target、lifecycle seed/cleanup 和 `main.py` wiring 不再直接持有 runtime store。
  - `tests/unit/personal_assistant/test_heartbeat_im_delivery.py`（扩展），覆盖 owner lazy-direct 首 content 前静默、`NO_REPLY` / `HEARTBEAT_OK` 静默、ack 回填后 delta。
  - `tests/unit/personal_assistant/test_cron_delivery_chain.py`（扩展），覆盖 cron owner-direct context seeding/cleanup 与 stream delivery。
  - `tests/unit/personal_assistant/test_external_visible_delivery.py`（扩展），覆盖 external main path when IM offline、background/control visible delivery 和 session event notification 抽取后行为。
  - `tests/unit/personal_assistant/test_gateway_im_resilience.py`、`tests/im_service/unit/test_gateway_handler.py`、`tests/im_service/integration/test_gateway_websocket_api.py`（保留/必要时扩展），覆盖 transport/IM handler 行为不变。
- 落层/目录/marker：`tests/unit/`、`tests/im_service/unit/`、`tests/im_service/integration/`，marker：无。真进程 live 验收作为一次性证据记录在 `progress.md`，不进套件。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：worktree 隔离栈 live run 日志、HTTP/WS/DB 核对命令输出摘要、必要截图/日志路径；不提交到 `tests/`。

前端 UI：N/A。本 milestone 不改前端客户端面；Web IM live 路径通过同一 HTTP/WS 后端入口和 DB/事件核对验证用户可见 running/final 结果。

## Roadpoints

### R1 — Typed run delivery context and lifecycle

- 状态: DONE
- 步骤:
  - 新增 `src/personal_assistant/gateway/runtime_delivery/context.py` 与 lifecycle helper，表达 `RunDeliveryTarget(shadow|owner_direct|none)`、`RunDeliveryContext`、`RunDeliveryContextStore`。
  - 调整 relay accepted/completed/failed/cancelled cleanup 走 context store；保留 receipt/report/Feishu ack 行为。
  - 让 `main.py` 只 wiring lifecycle callback，不直接创建裸 `_run_context_store`。
- 验证:
  - `pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`

### R2 — Kernel event observer extraction

- 状态: DONE
- 步骤:
  - 把 `_build_kernel_event_observer()`、bubble roll、ack extraction、external mirror helpers 移入 `runtime_delivery/observer.py`。
  - 让 observer 消费 typed context store，同时保留 running/message/tool/permission/reconcile/external mirror 行为。
  - 补 owner lazy-direct 回归：首 content 前无 `turn_start`、`NO_REPLY` / `HEARTBEAT_OK` 静默、ack 后回填并继续 delta。
- 验证:
  - `pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py`

### R3 — Background/session delivery extraction and build wiring

- 状态: DONE
- 步骤:
  - 把 `_build_bg_reply_sender()`、`_build_session_event_callback()` 和 reply-context delivery helpers 移入 `runtime_delivery/background.py`。
  - 调整 `build_runtime()` 使用 runtime delivery factory/context store，`main.py` 保留 dependency injection wiring。
  - 补 background/control visible reply 与 session-event notification 行为回归。
- 验证:
  - `pytest tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`

### R4 — Gates and live-critical verification

- 状态: DONE
- 步骤:
  - 跑派发要求的七文件门禁。DONE：112 passed, 2 warnings。
  - 在 milestone worktree 运行 worktree 隔离 IM + Gateway 真栈，按 design.md runbook 验 Web IM trigger -> running/final、Gateway/IM restart/reconnect、cron owner-direct 有内容冒泡。DONE，详见 `progress.md` R4。
  - heartbeat 主动冒泡真栈按仓内既有 `strict xfail` 复现 #126；本 milestone 不伪装为通过。
  - Feishu/Lark 若有真实凭证则跑真实平台入站；缺凭证则在 `progress.md` 明确标记 Feishu-specific 未验，不用伪造 inbound 冒充。DONE：本隔离栈未配置 Feishu/Lark channel/凭证，仅记录未验，不伪造。
  - 合入 unit 分支后跑 `pytest -m "not e2e"`。DONE：3325 passed, 2 skipped, 22 deselected, 16 warnings。
- 验证:
  - `pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py`
  - `pytest -m "not e2e"`（unit 集成分支）
