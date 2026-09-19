# Code Review: refactor-568-tool-event-projection

## Round 1

- reviewer: `/root/static_review`，未参与受审实现；caller 明确同时派发 code review 与 verifier，两类结论分别记录。
- review_mode: `full`
- executed_base: `4394ad4246b2ec3324e2c8aa219212dc0ec2ff75`
- validated_at: `151928fed7d894114b89c851cce8b621872e64d7`
- 范围：完整 `base..head` 的 5 文件 diff，以及 motivation、design、implementation、current Gateway/IM specs 和受影响测试。无 spec delta；未改源码、测试或设计。

```json
[]
```

未发现需 maintainer 处理的具体缺陷。`ToolCallProjector` 只接手已获准的 start/end 解析、in-flight map 和 terminal reconcile；observer 仍保留 shadow-before-live、在线门控、Workflow binding、task-tracker 及 await/detach。逐字段与基线对照：shadow end 继续省略缺失的 `reason`、`output`、`duration_ms` 和 `approval`，live end 继续带 `reason/output/duration_ms` 的 null 形状并 trim 分类；live-only `pending_revalidation` 仅在在线投影后写入运行快照；异常收口仍取走未完成 call、保留 input/presentation，并不重写已 `tool_end` 的 call。

新增行为测试从 observer 与真实 SQLite shadow store 同时观察 durable/live 目的地，覆盖 end 字段差异及 connected/offline revalidation；既有 reconcile 和 presenter 回归仍经过当前接线。独立执行：`PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/unit/personal_assistant/test_tool_delivery_projections.py tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py tests/unit/personal_assistant/test_tool_end_detail_passthrough.py`，结果 `21 passed`；Ruff 和 `git diff --check` 通过。implementation.md 记录的 89+4 行为保持证据可复用。

caller 在同一冻结版本提供的可复用 CI 证据：`pytest -m 'not e2e' -n 4 --dist worksteal` 为 `3992 passed / 178.84s`（`/tmp/refactor568-pytest.log`）；frontend 的 `npm ci`、`npm audit --audit-level=critical` 和 `npm test -- --maxWorkers=2` 均通过（`83 files / 770 tests / 125.46s`，`/tmp/refactor568-frontend.log`）；`docs-check` 为 `242 maintained / 73 routes`，Ruff 全仓检查与 format check（1082 files）通过。这是 caller 执行、我已核对末尾结果的证据；独立产品验收仍由其专属 reviewer 报告。

## Round 2

- reviewer: `/root/static_review`，未参与 A1 实现；caller 明确派发 patch code review 与 delta verification。
- review_mode: `patch`
- executed_base: `4394ad4246b2ec3324e2c8aa219212dc0ec2ff75`
- validated_at: `34ff1a2cedfac2224ec88661bc19b54d4dded4c0`
- diff_range: `151928fed7d894114b89c851cce8b621872e64d7..34ff1a2cedfac2224ec88661bc19b54d4dded4c0`（中间 `3b4ff2ad9` 仅收录验收/设计/首轮报告）。

```json
[
  {
    "file": "tests/unit/personal_assistant/test_im_reply_image_delivery.py",
    "line": 128,
    "summary": "[P2] 终态清理回归未经过 coordinator 的两处授权接线",
    "failure_scenario": "A1 的修复依赖 SessionRunCoordinator.stop:1319-1322 首次传入 terminal_cleanup=True，以及 _await_terminal_run:3109-3111 在 cancelled 时按 _user_interrupted_runs 保留该授权。新增六个用例却直接调用 ContextStore.suppress(..., terminal_cleanup=True)：test_stopped_run_closes_existing_tools_without_reopening_output:156,159 模拟这两步，test_stop_cleanup_cannot_publish_content_or_target_another_bubble:201 也直接授予授权。既有 test_user_stop_reconciles_on_original_consumer_and_cleans_marker:175-206 没有 delivery_context_store。任一 coordinator 调用退回普通 suppress，六项仍会通过，而真实 /stop 会重现 R2-W1 并再次吞掉 reconcile。请在 coordinator 生命周期测试中注入真实 context store 和 observer/writer，覆盖 stop→cancelled→reconcile 以及 stop→reset/generation advance→late cancelled；从实际 frame 断言原 bubble 仅收到 failed tool/bodyless completion，reset 路径不发送。",
    "review_mode": "patch",
    "status": "CONFIRMED"
  }
]
```

其余 A1 接线与设计一致：`context.py:406-429` 只在 active/已有授权且 generation 未失效时保留 cleanup；observer `696-699` 仅为该授权的 reconcile 穿过 revoked gate；`image_connection.py:92-104` 要求同一非空 message_id、failed tool 或 `final_content is None`，并在 completion 前清除缓存 bubble，故不会回填正文或创建新气泡。`stop:1319-1322` 与 cancelled `3109-3111` 的实际调用也都传入设计规定的事实；上述问题是缺少把二者连到可观察结果的长期回归保护。此前 R1 projector ownership、双 schema、离线/顺序结论 retained。独立执行相关 19 项回归与 A1 文件 Ruff 通过，`git diff --check` 通过；caller 的 60 项窄套件和 Python 全量运行不改变此覆盖缺口。
