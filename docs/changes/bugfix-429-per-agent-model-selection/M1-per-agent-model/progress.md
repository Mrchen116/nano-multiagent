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

## R1 — 内核 model 透传链

- Context: model 当前固化在 loop.py:302 `self._model`（build_kernel 一次性），到内核边界后续每轮无 per-run 入口。submit 异步排队 + 内核续跑（registry:641）→ model 不能只作同步透传参数。
- Decision: RunRecord 加 `model` 字段；`kernel.submit/runs_registry.submit(model)` 存入；`_run_worker_async` 从 `RunRecord.model` 取并传 `runtime.run(model)`；续跑 self.submit 复用本 run `run_model`；runtime.run → _run_locked → _execute_loop 透传 → `loop.run(model_override)`；loop 用 `model_override or self._model`（self._model 暂留作迁移兜底，R2 移除对话用途）。
- Rationale: model 落 RunRecord 是因为后台 worker（create_task）与续跑在同步 submit 返回后才执行，同步参数取不到；续跑复用本 run model 正好落实 incident 边界「进行中 run 用原模型跑完」。R1 保留 self._model 兜底让既有调用点（产品/测试）零改动即可编译，分步推进。
- Evidence:
  - Tests: 新增红测 `test_loop_model_override_routes_request_model`（loop）+ `test_runs_registry_threads_model_into_record_and_runtime`（submit→RunRecord.model→runtime）先红后绿；`pytest -m "not e2e"` 全树 2773 passed/2 skipped 全绿（基线 2771，+2 新测）。RuntimeRunner Protocol + 受影响 stub（test_runs_registry/test_run_cancel/test_kernel_cancel_permission/test_abort_priority/test_run_origin）补 model 参数。
  - Entry: N/A（R1 是内核内部透传，真实入口验证在 R3 Gateway 接通 + R7 live）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 单测即 regression；live 端到端留 R7。
  - Visual/Interaction: N/A
  - Lint: ruff check + format 通过（registry.py 经 ruff format 重排 model 字段位置）。
- Rollback: 回退到本 milestone plan commit（R1 前）。
- Commits: C1=test 红测, C2=feat 透传链, C3=本次 docs。
- Next: R2 多 client 按 provider 路由 + provider_of + 移除 loop self._model 对话用途 + reconfigure_llm/bind_llm_client 退役。
