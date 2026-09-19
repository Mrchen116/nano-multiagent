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
