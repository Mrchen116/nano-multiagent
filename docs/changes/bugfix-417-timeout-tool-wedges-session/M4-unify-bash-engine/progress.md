# bugfix-417-M4 — Progress

> 启动上下文核实（§2.3 完成）：
> - 死路确认：`run_stream`/`_run_legacy_sync` 仅被 bash.py 自身 `wiring is None` 分支 + 单测调用，零其它生产调用方（loader.py 无引用）。
> - M3 下游链全活：executor `run_coroutine_threadsafe` 桥（tools/registry.py:213）、realtime_stream `on_tool_execution_update→run_heartbeat`、liveness 模块 LLM-await（loop.py:320）+ permission ticker（runtime.py:1448）、gateway `stalled`（inbound_pipeline.py:869）、前端徽标（tool-calls-panel.tsx:83）。
> - M4 = 把 bash 源从死路换到 ShellRunner 接活链 + 删死路 + 端到端守卫。
