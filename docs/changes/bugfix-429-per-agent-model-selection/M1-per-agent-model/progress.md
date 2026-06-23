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

## R2 — 多 client 按 provider 路由

- Context: 决策3 要求内核按模型注册的 provider 路由到对应 client，不依赖 proxy「一个模型名多格式通吃」。当前内核只持单 client（build_kernel 建一个 active client）。
- Decision: model_registry 加 `provider_of(model)` 反查（未注册 raise，禁兜底）；AgentLoop 加 `llm_clients: dict[provider,client]`，`_client_for_model` 按 `provider_of(active_model)` 选 client；build_kernel 遍历 `llm.providers` 各建一 client（同 provider 内 base_url 固定、model 随 request.model 变，故一 provider 一 client）；runtime 透传 llm_clients 给 loop。无 map 时回退单 client（单测/override 路径）。
- Rationale: dict[provider,client] 是 design 决策3 拍死的形态（否决选项A 单 client 通吃）。team-lead 复述确认保持此形态。同 provider 多 model 共用 client（base_url 同），跨 provider 才换 client。
- 决策（实施期）: reconfigure_llm / bind_llm_client 的退役**推迟到 R6**。它们的唯一真实调用链是 kernel.reconfigure_llm ← CLI llm-config set（commands.py:511）；loop.bind_llm_client ← runtime.reconfigure_llm。三者串成一条链，只有 CLI 改自维护 current model 后才无悬挂调用方。R2 强退役会让 CLI + 多个 contract/CLI 测试同时变红，违反逐 roadpoint 绿门禁。故 R2 只做多 client 路由，退役随 R6 CLI 一并做。design 决策3 的退役目标不变，只是落点挪到 R6。
- Evidence:
  - Tests: 新增红测 `test_provider_of_reverse_lookup` / `test_provider_of_unknown_model_raises`（model_registry）+ `test_loop_routes_to_client_of_models_provider`（loop 路由）先红后绿；`pytest -m "not e2e"` 全树绿（修一处 contract 行号锚定失配后 2775+ passed/2 skipped）。
  - Entry: N/A（R2 内核内部；真实跨 provider 路由的端到端证据走 R7 live：gpt→openai_compat over the wire）。
  - Frontend State Matrix / Browser QA / Visual: N/A
  - E2E/Regression: loop 路由单测即 regression；跨 provider over-wire 留 R7。
  - Lint: ruff check + format 通过（loop.py 经 format）。
  - Trap: contract `test_no_hardcoded_workspace_dirname` 白名单行号锚定，R2 的 __init__/build_kernel 插行使 runtime.py:180→185、kernel.py:483→501 失配，已更新 pin（[[project-ci-ruff-and-line-pinned-whitelist]]）。
- Rollback: 回退到 R1 C3 commit。
- Commits: C1=test 红测, C2=feat 多 client 路由 + 行号 pin, C3=本次 docs。
- Next: R3 Gateway 三入口传 model（inbound 主轮/stop + heartbeat/cron 经 shim）。
