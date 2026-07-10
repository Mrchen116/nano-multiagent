# fix/refactor-387-heartbeat-im-report — Progress

## Context

Reviewer 反馈循环 Round 5 acceptance-pa.md 报告 heartbeat 触发时 asyncio event loop 嵌套冲突。
上一轮 fix-heartbeat-async 修复了第一层 bug（`_KernelClientShim.create_session` 用 `run_until_complete`
在运行中 loop 内炸 RuntimeError）。

本次 fix 对应第二层 bug（async 修好后 heartbeat 真触发，于是暴露 heartbeat 完成报告路径——
即 `_publish_heartbeat_product_reports` / `_build_heartbeat_product_reports` 桥）：

- 该桥构造 `conversation_id=heartbeat:<agent_id>`、`message_id=run_id` 合成 FK 引用
- IM events 表外键硬引用 messages 表，导致 `sqlite3.IntegrityError: FOREIGN KEY constraint failed`
- IM `_handle_report` 将异常冒泡出 WS dispatch 层，关闭连接
- Gateway 侧 `im_connection._listen_once` 对下行 `type=error` 帧执行 `raise ValueError`
  → `run_forever` except → `_mark_disconnected` → 断线重连循环

该桥自 M138 引入后从未成功投递过——每次触发必崩。

## Decision

### A. 主 bug：删除畸形 node.report heartbeat 报告桥

删除：`_publish_heartbeat_product_reports`、`_build_heartbeat_product_reports`、
`HeartbeatRunner.build_product_reports` 协议方法及 `HeartbeatRunnerImpl.build_product_reports` + `_product_reports` 累积。

heartbeat run 执行本身（scheduler.tick → kernel session）保留不动。

把 heartbeat 结果展示到 IM 会话是独立特性（需要把 heartbeat run 绑定到真实 IM 会话 + 走 streaming 管线），
超出 refactor 行为对齐范围，记录为 out-of-unit 特性缺口。

### B. IM 侧健壮性

`_handle_report`：
- 捕获 `node_id` 解析异常 → 返回 `{"type": "error", ...}` ack，连接不关闭
- 捕获持久化异常（IntegrityError 等）→ `_logger.warning`，返回正常 ack，连接存活

### C. Gateway 侧健壮性

`im_connection._listen_once`：新增 `type=error` 分支：记录到 `events` 后 return，不再 raise ValueError。

## Rationale

node.report 持久化硬性要求真实 `(conversation_id, message_id)` 外键行；heartbeat run 跑在新建
的 kernel session 里，根本不绑定任何真实 IM 会话。无论怎么补字段都无法满足外键——
在数据模型层面这条路就是错的。

## Evidence

### Tests

C1 红测试（两条回归）：
- `test_im_connection_does_not_disconnect_on_downstream_error_frame`：收 error 帧 → 不 raise，后续 relay.message 正常分发
- `test_gateway_websocket_malformed_node_report_does_not_close_connection`：畸形 node.report → IM 返回 error ack，后续合法 report 正常 ack

C2 全测试树：`pytest -m "not e2e"` → 2341 passed, 0 failed

### E2E 实证（heartbeat interval:10s，≥2 tick，真实 IM）

```
IM_PORT=62898（ephemeral）
Gateway: PID 23839，--foreground --auto-bind
Agent workspace: .e2e-gateway-workspace/hb-agent/
HEARTBEAT.md: interval: 10s
```

等待约 65s 后 Gateway log（从无到有，说明 heartbeat tick 真正触发了）：

```
INFO node wt-fix-heartbeat-e2e auto-bound to IM
  → NANO_MULTIAGENT_AUTO_BIND=1 confirmed bind for http://127.0.0.1:62898.
run_failed | error='LLM generate exceeded 20 retries: anthropic transport error', run_id='run_84e4ad70b91bf50c', session_id='sess_9e7db822e4160078', ...
run_failed | error='LLM generate exceeded 20 retries: anthropic transport error', run_id='run_e9f5ee1c701e401c', session_id='sess_cf5ff686464edeef', ...
run_failed | error='LLM generate exceeded 20 retries: anthropic transport error', run_id='run_2249505da3e85eee', session_id='sess_80c55d2f58029c30', ...
run_failed | error='LLM generate exceeded 20 retries: anthropic transport error', run_id='run_fcd9b7c715eac9b2', session_id='sess_761e7f6ea3a3bfe0', ...
```

4 个独立 run（≥2 tick），LLM 因 e2e 环境无 provider 失败属正常，heartbeat scheduler 成功提交 run。

IM WS 全程存活证据（IM log 完整内容，无任何 disconnect/error/close）：
```
INFO:     127.0.0.1:63128 - "WebSocket /im/ws/gateway" [accepted]
INFO:     connection open
INFO:     127.0.0.1:63129 - "POST /im/v1/auth/refresh HTTP/1.1" 200 OK
INFO:     127.0.0.1:63130 - "GET /im/v1/nodes HTTP/1.1" 200 OK
INFO:     127.0.0.1:63130 - "POST /im/v1/bind HTTP/1.1" 201 Created
INFO:     127.0.0.1:63130 - "POST /im/v1/bind HTTP/1.1" 201 Created
（整个 65s 期间无 connection closed / error / node_id must be / FK constraint）
```

已确认：
- 无 `node_id must be...` error frame
- 无 `FOREIGN KEY constraint failed`
- 无 `unsupported downstream message type: error`
- 无断线重连循环

## Out-of-unit 特性缺口

"heartbeat/cron 运行结果未展示到 agent 的 IM 会话（M138 node.report 桥畸形/从未生效）"——
这是后续 unit 的特性，需要把 heartbeat run 绑定到 agent 真实 IM 会话并走 streaming 管线。

## Rollback

git revert 4dac0907（C1）+ 2a49702b（C2）恢复到上一稳定态。

## Commits

- C1=4dac0907（test: 补红测试——畸形 node.report 不断连 + 下行 error 帧不触发重连）
- C2=2a49702b（fix: 删除畸形 heartbeat node.report 桥 + 双侧健壮性加固）
- C3=（本 commit）

## Test Tech Note（给下一位 reviewer 的教训）

原来的 `test_build_heartbeat_product_reports_*` 和
`test_gateway_runtime_publishes_heartbeat_product_reports_to_im` 用 mock IM（`sent_frames` list），
从未走真实 events 表 FK 检查——这正是 FK bug 漏网的原因。删除这些测试并在
`test_gateway_heartbeat.py` 头部留下这条教训的注释。
