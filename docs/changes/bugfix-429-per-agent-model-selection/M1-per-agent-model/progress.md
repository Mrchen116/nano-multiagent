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

## R3 — Gateway 三入口传 model

- Context: 内核 submit 现收 model（R1）但 Gateway 三个发起新 run 的入口（inbound 主轮 :285、stop :705、heartbeat/cron 经 shim :2001）都没传。决策2 要求产品层每轮提供 model。
- Decision:
  - inbound_pipeline 构造注入 `product_default_model=config.llm.default_model`；新增 `_resolve_model(agent_id)`：每轮取 `self._agents[id].default_model`（config.sync 经 register_agent 实时更新该 dict → 旧会话下一轮自动用新模型），缺省回退 product_default；主轮 + stop 两处 submit 传 `model=self._resolve_model(agent_id)`。
  - heartbeat/cron 经 shim：`_KernelClientShim` 加 `product_default_model` + submit_message 加 `model` / `agent_id` 参数；解析 `model = 显式model(heartbeat 传 agent.default_model) or agent_id→default_model(cron 传 agent_id) or 产品默认`。heartbeat_scheduler 传 `model=agent.default_model`，cron_runner 传 `agent_id=self._agent_id`（cron 手里有 agent_id 无 agent 对象，让 shim 用 _agents_by_id 反查）。
- Rationale: team-lead 确认「调用方解析、shim 透传」优于 design 的「shim 反查 session→agent」。「旧会话用新模型」靠每轮取 self._agents 最新值天然满足（决策1）。fallback 集中在产品层（inbound 在 pipeline、heartbeat/cron 在 shim），内核零默认。
- Evidence:
  - Tests: 新增 `test_inbound_pipeline_submits_agent_selected_model` / `..._falls_back_to_product_default_model` / `test_scheduler_passes_agent_model_to_submit` 先红后绿；`pytest -m "not e2e"` 全树 2779 passed/2 skipped 全绿。多处 kernel/submit_message 测试 fake 补 model 参数（_pipeline_helpers / im_service integration helpers / cron_delivery / pipeline_observer / cron_run_origin）。
  - Entry: 真实入口验证（IM 发消息 → 选定 model 真生效）留 R7 live；R3 单测覆盖「submit 携带正确 model」的契约。
  - Frontend / Browser / Visual: N/A
  - E2E/Regression: 单测即 regression；端到端 R7。
  - Lint: ruff check + format 通过（main.py 经 format）。
  - Trap: 用脚本批量给 fake 注入 model 参数时，正则按 `):` 收尾误匹配到方法体内行（真实签名是 `) -> Any:`），在 3 个文件 return 后插了死代码 `model=None,`，已手工修正——批量改测试 fake 签名要核对每处落点。
- Rollback: 回退到 R2 C3 commit。
- Commits: C1=test 红测, C2=feat Gateway 三入口 + fake 适配, C3=本次 docs。
- Next: R4 链路B 动态新建 agent default_model 持久化（加日志钉真因）。

## R5 — IM + 前端 provider 展示

- Context: list_models() 带 provider，但 upstream_reporter.py:87 flatten 成纯 name，下游全链路 list[str]，前端下拉只显 name。incident「IM 下拉展示 provider」需求。
- Decision:
  - Gateway：`_models_from_kernel` 返回 `tuple[{name,provider}]`（保 list_models 的 provider）；ReporterCapabilities.models 结构化；删死代码 `_dedupe_preserve_order`。
  - IM：新增 `ModelOptionResponse{name,provider}` + `coerce_model_options`（容忍旧 Gateway 纯 str → provider=""）；agents.py/nodes.py capabilities `models` 改 `list[ModelOptionResponse]`。
  - 前端：`ModelOption{name,provider}` 类型；`normalizeModelOptions`/`resolveModelOptions` 透传 provider；detail/create 下拉渲染 `<model> · <provider>`，缺 provider 降级只显 name。
- Rationale: provider 在内核就有，只需阻止下游丢弃 + 各层带过去。容忍旧 str 形态保证滚动升级不炸。
- Evidence:
  - Tests: 红测 `test_node_capabilities_models_carry_provider`（Gateway）+ 前端 `bugfix-429 R5: model dropdown labels...`（断言 option 文案含 provider）先红后绿；前端 65 vitest 全绿 + `npm run build`(tsc+vite) 通过；`pytest -m "not e2e"` 全树绿（修 2 处：im_service contract shape + capability golden）。
  - Entry: **live 验证** —— 重启 e2e 栈后 `GET /im/v1/nodes/{node}/capabilities` 的 models 端到端带 provider：kimi/doubao→anthropic、gpt-5.5→openai_compat（Gateway reporter → IM API 全链路）。
  - Frontend State Matrix: default（option 显 `name · provider`）✓ / empty（[] → 仅平台默认占位）✓ / missing provider（降级只显 name）✓ 单测覆盖；mobile/long-content 视觉留 R7 截图。
  - Browser QA: 留 R7（连同 model 真生效一起做真实浏览器旅程 + 截图）。
  - E2E/Regression: 后端 reporter/contract 单测 + 前端组件测试即 regression；live capabilities 已验。
  - Visual/Interaction: 下拉 provider 标注截图留 R7。
  - Lint: ruff + tsc 通过。
  - Trap: byte-identity golden `test_capability_payload_baseline` 锚定 models 旧 list[str]，改结构化后同步 golden（[[project-golden-host-volatile-and-unpinned-deps-ci-red]]）。
- 契约层影响（待 orchestrator，§0.13 不由 worker 写）：`docs/specs/im/spec.md` capabilities models 携带 provider。
- Rollback: 回退到 R4 commit。
- Commits: C1=test 红测, C2=feat 后端+前端 provider 展示, +golden 修复, C3=本次 docs。
- Next: R6 CLI 自维护 current model + reconfigure_llm/bind_llm_client 退役（先问 team-lead /model UX）。

## R7 — 端到端 live 验证（进行中，已 PASS 核心 + 暴露决策3冲突）

- Context: live-critical 硬门槛——IM 选 gpt 的 agent 对话 → LLM proxy 日志该请求 model==codex_oauth:gpt-5.5。
- 环境: worktree e2e（scripts/e2e-up.sh，ephemeral IM + Gateway + 真 LLM proxy@4000）。
- **核心 PASS**: IM PATCH default-agent default_model→codex_oauth:gpt-5.5（真配置路径）→ 直聊发消息 → proxy 日志 `/Users/czj/Repos/LLM_PROXY/logs/session/2026-06-23_22-08-47_131_sess_0279fa047455b864/*-req-anthropic_messages.json` → `model=codex_oauth:gpt-5.5`，anthropic_messages 协议，回复完成无错。所选模型真生效。
- **暴露的决策3冲突（已 systematic-debugging 钉死根因，上报 team-lead 待决策）**:
  - config 把 codex_oauth:gpt-5.5 声明在 openai_compat provider；决策3 多 client 路由 → OpenAICompatClient → openai_chat 协议 → proxy 报 `profile=kimiCoding 不支持协议 openai_chat`。
  - 实测：curl /v1/chat/completions（openai_chat）同 model 报同错；curl /v1/messages（anthropic）同 model 成功返回 pong。即 proxy 只用 anthropic 格式服务 gpt-5.5。用户原话亦「anthropic 格式调 gpt」。
  - 根因：config 把 gpt 声明成 openai_compat 与现实（anthropic 格式）不符。决策3 本身没错（按声明路由），错在声明。
  - 旧内核单 client 固定 anthropic 故一直能用；决策3 多 client 忠实按 openai_compat 声明路由反而打断。
  - 验证修复（worktree config）：gpt-5.5 移到 anthropic provider + 删空 openai_compat → 重启 GW → live PASS（上面证据即此配置）。
  - 附带发现：空 provider 会让 build_kernel client 构造 + model_registry.resolve_model_metadata 崩（next(iter()) on empty）。选 A 删 provider 规避；若要支持空 provider 需 build_kernel 跳过（小改）。
  - 待 team-lead 决策 A（改 config 把 gpt 挪 anthropic，授权动主仓 config.yaml）/ B（不推荐）。
- Next: 待 team-lead 两条决策（R6 CLI A/B/C + R7 config A/B）后收口；补兜底默认/跨 provider live 证据。

### R7 live 证据汇总（全 PASS，config 采 A 形态下）

三条 incident 核心 Scenario 均经真实 IM→Gateway→kernel→LLM proxy 端到端验证（proxy 日志取证）：
1. 选定非默认模型生效：default-agent PATCH→gpt-5.5，对话 → proxy req `model=codex_oauth:gpt-5.5`（anthropic_messages）✓
2. 没选默认兜底：Arch（default_model=None）对话 → proxy req `model=kimiCoding:K2.6`（产品默认）✓
3. 改模型后旧会话用新模型：同一已存在会话 b985…，default-agent 模型 gpt→kimi 后再发 → proxy req `model=kimiCoding:K2.6`（旧会话切到新模型，非锁死旧值）✓

证据路径：/Users/czj/Repos/LLM_PROXY/logs/session/2026-06-23_22-* 各 *-req-anthropic_messages.json 的 model 字段。
跨 provider（openai_compat client over wire）live 未能验证——proxy 不支持 gpt 的 openai_chat 协议（见上「决策3冲突」），采 A 后 gpt 走 anthropic client，openai_compat client 路径目前无可用上游可 live 验（单测已覆盖路由选择）。

## R6 — CLI 自维护 current_model + reconfigure_llm 退役

- Context: 决策2「内核零默认、model 每轮由消费者传」+ 决策3「reconfigure_llm 退役」。reconfigure_llm 唯一调用链是 CLI llm-config set → kernel.reconfigure_llm → runtime.reconfigure_llm → loop.bind_llm_client。
- Decision（team-lead 拍 B + 两处纠正）:
  - CLI 自维护 current_model：`_resolve_cli_current_model(kernel.get_llm_config().model)`（model 由 --model/env 经 build_kernel 定），`_run_text_mode`/`_run_repl`/`_send_message_async`/`text_runner.run_text` 每轮 submit 传 model。
  - 退役 kernel.reconfigure_llm + runtime.reconfigure_llm + loop.bind_llm_client（整条链）。
  - 移除 `llm-config set` 子命令（argparse + 处理体），保留 `llm-config get`。否决 C（bugfix 不新增 CLI UX，/model REPL slash 留未来 unit）。
- Rationale: model per-run 后一次性子命令 set 无持久载体（会变 design 否决的选项A半残）；清理失效命令是对的。get_llm_config 仍报 build-time active connection 供脚本/选择器。
- Evidence:
  - Tests: 红测 `test_run_cli_text_mode_submits_current_model`（CLI submit 带 get_llm_config().model）先红后绿；删 2 个 reconfigure 行为 contract + 3 个 llm-config set CLI 测试 + stub reconfigure 方法；surface contract 改断言 reconfigure_llm 不存在；error contract 改 ValueError 触发 input 层；`pytest -m "not e2e"` 全树绿（修 2 处：error contract set→ValueError、hardcoded-dirname 行号 1232/1233→1202/1203）。
  - Entry: CLI 真实入口验证留收尾（CLI 非本 bug 主路径；单测覆盖每轮传 model 契约 + 退役后无悬挂调用）。
  - Frontend/Browser/Visual: N/A
  - Lint: ruff check + format 通过；冒烟 import 通过。
  - Trap: 退役删行使 commands.py `.nanocode` 行号下移 30 行，line-pinned 白名单失配，已更新（[[project-ci-ruff-and-line-pinned-whitelist]]）。
- 契约层影响（待 orchestrator，§0.13）：
  - **cli/spec.md**：`llm-config set` 子命令移除（用户可观察变化）；set scenario（无字段→input 错误 JSON）删除/改写。team-lead 已认领改 cli delta + canonical。
  - **kernel/spec.md**：删 reconfigure_llm Scenario（旧 :230-232）；决策5「model 维持 kernel 级」表述改为「model 随 run 由消费者每轮提供」；submit 新增必填语义 model。
- Rollback: 回退到 R5/R4 commit。
- Commits: C1=test 红测, C2=refactor 退役+CLI每轮传+适配, C3=本次 docs。
- Next: R7 config 决策（决策3冲突，gpt 挪 anthropic，需 team-lead 授权改主 config.yaml）后做最终 live + 收尾集成。
