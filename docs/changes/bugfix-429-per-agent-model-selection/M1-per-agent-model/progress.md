# bugfix-429-M1 — Progress

> 实施期记录。每个 roadpoint 完成后补齐。

## 启动勘察（开工前）

- 基线：`pytest -m "not e2e"` 2771 passed / 2 skipped / 6 deselected 全绿。
- 内核透传链确认：`kernel.submit` → `runs_registry.submit` → `RunRecord` → `_run_worker_async`（后台闭包）→ `runtime.run` → `_run_locked` → `_execute_loop` → `loop.run` → `_llm_client.generate(model=...)`。当前 loop 用 `self._model`（全局固化，loop.py:302）。
- 续跑点：registry.py:641 `self.submit(...)` 处理 stranded 消息——必须复用本 run RunRecord.model。
- 多 client 可行性：同 provider 内 base_url 固定（client 构造时定），model 随 `request.model` 变；client.generate 已用 request.model + resolve_model_metadata 取 per-model 元数据。故一 provider 一 client，跨 provider 才需不同实例。
- Gateway submit 来源：inbound_pipeline 两处有 `self._agents[agent_id].default_model`（需注入 product_default）；heartbeat/cron 经 shim.submit_message（shim 无 session→agent 反查，但调用方 heartbeat_scheduler:462 / cron_runner:145 手里有 agent）。
- IM provider 丢失点：upstream_reporter.py:87 `[m.name for m in kernel.list_models()]`，下游全是 list[str]。前端下拉 agent-detail/create-page 只渲染 model name。
- 「改模型后旧会话用新模型」天然满足：每轮 submit 取 `self._agents[id].default_model` 最新值，config.sync 经 register_agent 实时更新该 dict。
