# M2 隔离真栈证据

## 环境与口径

- 日期：2026-07-15。
- 代码：`milestone/refactor-463-M2`，真 IM + 真 Gateway 由 `scripts/e2e-up.sh` 在 pytest 临时目录、高位端口、隔离 config/workspace 中启动；LLM 经本机 `:4000` 代理。
- 命令统一显式把主仓 `.venv/bin` 放到 `PATH`，避免 `e2e-up.sh` 的子进程落到不含 PyYAML 的系统 Python。
- 图片、active shutdown、后台回信使用真 IM REST/WS 与独立 Gateway 进程；queued-before-submit 与 IM-offline 使用 `build_runtime()` 构造真 GatewayRuntime/Kernel。queued 驱动只在一次性测试中暂停首项 binding，以确定性制造真实 FIFO pending 项；临时驱动执行后已删除，未进入回归套件。

## 真入口结果

### 图片、恢复与 active shutdown

命令（一次性驱动已删除）：

```bash
PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" \
NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 \
pytest -xvs tests/e2e/critical_paths/test_refactor463_m2_live_temp.py::test_live_images_and_shutdown_active
```

结果：`1 passed in 31.61s`。

```text
M2_LIVE_IMAGE_SHUTDOWN={
  "valid_reply": "IMG6D8A0156",
  "corrupt_reply": "这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。",
  "before": "sent",
  "after": "failed"
}
```

- 有效 PNG 到达模型并返回哨兵；损坏 PNG 返回既有固定文案，不调用模型。
- 同一会话随后纯文本恢复轮返回 `REC9F8FBB42`。保留的 session JSONL 对账只有有效图片占位轮与恢复文本轮，损坏图片轮没有写入 Kernel history。
- 长前台 Bash 已出现 `tool_call.upserted` 后向 Gateway 发 SIGTERM；对应 IM relay 从 `sent` 进入 `failed`，不再悬空。

### 后台结果回原会话且不重复

```bash
PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" \
NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 \
pytest -xvs tests/e2e/critical_paths/test_refactor463_m2_live_temp.py::test_live_background_returns_to_original_conversation_once
```

结果：`1 passed in 36.27s`。

```text
M2_LIVE_BACKGROUND={
  "conversation_id": "a438d94202554fa09b44bff05e729c70",
  "matching_reply_count": 1,
  "reply": "BGONCEC060E0A7"
}
```

后台 Bash 完成后的哨兵回到发起会话；收到后继续观察 8 秒，同一会话中含该哨兵的 agent 回复仍恰好一条。

### `/stop` 保持既有终态

```bash
PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" \
NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 \
pytest -xvs tests/e2e/critical_paths/test_stop_run_critical_path.py::test_stop_aborts_active_run
```

结果：`1 passed in 40.07s`。真前台 `sleep 45` 进入 tool call 后收到固定 `已停止当前操作。`，随后 20 秒未出现被中止 run 的完成哨兵。

### queued-before-submit 明确失败

```bash
PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" \
NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 \
pytest -xvs tests/e2e/critical_paths/test_refactor463_m2_live_temp.py::test_external_queue_shutdown_with_im_absent
```

结果：`1 passed in 2.64s`。

```text
M2_LIVE_QUEUE_SHUTDOWN={"lifecycle": [
  ["first", "accepted", null],
  ["second", "failed", "gateway_shutdown_before_submit"],
  ["first", "failed", "run was aborted"]
]}
```

首项已由 Kernel 接纳，第二项真实进入同 session FIFO 后才请求 shutdown；第二项未调用 Kernel，直接收到明确 failed lifecycle，首项也到达 terminal。

### IM 离线不阻断外部 channel

```bash
PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" \
NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 \
pytest -xvs tests/e2e/critical_paths/test_refactor463_m2_live_temp.py::test_external_channel_completes_with_im_absent
```

结果：`1 passed in 8.47s`。

```text
M2_LIVE_EXTERNAL_OFFLINE={"sent_count": 1, "reply": "OFFLINE651B70A9"}
```

配置中 `im_service=None`，本地 external adapter 经真 GatewayRuntime、真 Kernel 与真 LLM 完成一条且仅一条回复，runtime 正常返回 exit code 0。

## 最终回归门禁

```bash
pytest -q \
  tests/unit/personal_assistant/test_image_attachment_resolver.py \
  tests/unit/personal_assistant/test_background_subscription_manager.py \
  tests/unit/personal_assistant/test_inbound_dispatcher.py \
  tests/unit/personal_assistant/test_runtime_delivery_task_tracker.py \
  tests/unit/personal_assistant/test_gateway_shutdown_resource_graph.py \
  tests/unit/personal_assistant/test_inbound_pipeline_shutdown_terminal.py \
  tests/unit/personal_assistant/test_run_queue.py \
  tests/unit/personal_assistant/test_gateway_shutdown_order.py \
  tests/unit/personal_assistant/test_gateway_runtime_lifecycle.py \
  tests/contract/test_test_naming_and_size_contract.py
```

结果：`33 passed in 3.08s`。

```bash
ruff check src tests
pytest -m 'not e2e' -n 4 --dist worksteal --durations=20 --durations-min=0.5
```

结果：ruff 全绿；`3367 passed, 1 skipped, 22 warnings in 33.82s`。warnings 均为既有依赖的 deprecation / JWT 测试密钥长度提示。
