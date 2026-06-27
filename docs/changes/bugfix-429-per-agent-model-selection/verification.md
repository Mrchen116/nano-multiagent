# Verification Report: bugfix-429

> Round 1 — 2026-06-24

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 9/9 退出标准全覆盖 |
| Correctness | 6/6 requirement 有实现 + 测试覆盖 |
| Coherence | Followed（3 项关键决策均遵守） |

All checks passed. Ready for PR.

---

## Completeness

### Tasks: 9/9 complete

tasks.md 退出标准（隐式 task 列表）全部标记完成：

| 退出标准 | Roadpoint | 状态 |
|---|---|---|
| `kernel.submit(model=...)` 存入 RunRecord | R1 | DONE |
| loop 移除 `self._model` 对话固化，按 `model_override` 发请求 | R1/R2 | DONE |
| build_kernel 建 `dict[provider,client]`，`provider_of` 路由 | R2 | DONE |
| `reconfigure_llm` / `bind_llm_client` 退役；CLI `/model` 改自维护 | R6 | DONE |
| Gateway 三入口（inbound 主轮/stop + heartbeat/cron）全部传 model | R3 | DONE |
| 链路B：动态新建 agent default_model 写回用户实际 config | R4 | DONE |
| IM capabilities models 携带 provider；前端下拉展示 provider | R5 | DONE |
| `pytest -m "not e2e"` 全绿（2782 passed / 1 skipped） | R7 | DONE |
| live 端到端：IM 选 gpt-5.5 → proxy 日志 `model==codex_oauth:gpt-5.5` | R7 final | DONE |

### Spec requirement 覆盖

所有 6 条 incident requirement 均有实现：

1. agent 配置选定的模型真实生效 → 链路 A 内核透传链实现
2. 改模型后旧会话也用新模型 → `inbound_pipeline._resolve_model` 每轮取 `self._agents` 最新值
3. 没选模型时有默认兜底 → `_resolve_model` fallback 到 `product_default_model`
4. IM 模型选择展示 provider/格式 → R5 frontend `agent-detail-page.tsx:1298-1299`
5. 模型选择持久化 → R4 链路B `handle_agent_create` 写回 `source_path`
6. 切换边界（进行中 run 用原模型）→ 内核续跑 `registry.py:663` 复用 `run_model`

---

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| submit 携带 model 并在该 run 生效 | `registry.py:376`（RunRecord.model）→ `loop.py:189`（active_model） | `test_runs_registry_threads_model_into_record_and_runtime`（registry:129）、`test_loop_model_override_routes_request_model`（loop:147） | covered |
| 同一 run 内核续跑复用本 run model | `registry.py:621-663`（run_model 从 RunRecord 取，传 self.submit） | `test_runs_registry_threads_model_into_record_and_runtime` 中续跑路径验证 | covered |
| 跨 provider 类型都能生效 | `kernel.py:395-407`（build_kernel 建多 client）；`loop.py:129-143`（`_client_for_model` → `provider_of`）| `test_loop_routes_to_client_of_models_provider`（loop:R2 新增）；`test_provider_of_reverse_lookup`（model_registry:111） | covered |
| 改模型后旧会话用新模型 | `inbound_pipeline.py:790-801`（`_resolve_model` 读 `self._agents` 实时最新值） | `test_inbound_pipeline_submits_agent_selected_model`（pipeline:208）；`test_inbound_pipeline_falls_back_to_product_default_model`（pipeline:247） | covered |
| 没选模型时产品层兜底 | `inbound_pipeline.py:801`（fallback `self._product_default_model`）；`main.py:2021`（shim 同理） | `test_inbound_pipeline_falls_back_to_product_default_model` | covered |
| IM 下拉展示 provider | `agent-detail-page.tsx:1298-1299`（`providerSuffix = model.provider ? \` · \${model.provider}\` : ""`） | 前端 vitest（agent-edit.test.tsx 中 R5 新增组件测试，65 vitest 全绿） | covered |
| 模型选择持久化（链路B） | `main.py:507`（`handle_agent_create` 调 `_persist_agent_config`）；`main.py:670-705`（写回 `source_path`） | `test_handle_agent_create_persists_default_model_to_source_path`（config_sync:510）；`test_handle_agent_create_persists_to_default_config_path`（config_sync:582） | covered |
| CLI 每轮传 model | `commands.py:255-282`（`_resolve_cli_current_model` + 每轮 submit 传 model） | `test_run_cli_text_mode_submits_current_model`（test_cli_text_sse:148） | covered |
| heartbeat/cron 传 model | `main.py:2021`（shim 按 agent/agent_id 解析 model）；`main.py:1929-1939`（`product_default_model` 注入） | `test_scheduler_passes_agent_model_to_submit`（heartbeat_scheduler:130） | covered |
| 空 provider 健壮 | `kernel.py:406`（`if p.models` 跳过空 provider）；`model_registry.py:144`（`provider_of` 清晰 ValueError） | `test_build_kernel_tolerates_empty_provider`（contract:376）；`test_resolve_model_metadata_empty_provider_raises_clearly`（model_registry:81） | covered |

---

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策1：model 由产品层每个新 run 提供、存入 RunRecord，run 内复用 | 是 | `registry.py:75`（RunRecord.model 字段）；`registry.py:621-663`（续跑读 RunRecord.model）；`kernel.py:860`（submit 接收 model） |
| 决策2：内核不持有对话默认 model，所有新 run 的 model 由产品入口提供 | 是 | `loop.py:188-189`（`active_model = model_override or self._model`，self._model 仅作迁移兜底注明）；`inbound_pipeline.py:796-801`（产品层显式兜底）；CLI `commands.py:255`（自维护 current_model） |
| 决策3：内核按模型注册的 provider 路由 client；reconfigure_llm 退役 | 是 | `kernel.py:395-407`（多 client dict 建立）；`loop.py:129-143`（`_client_for_model`）；`grep 'reconfigure_llm\|bind_llm_client' kernel.py runtime.py` = 0 matches |

### 架构自洽性（§4.3）

- **依赖方向**：`inbound_pipeline` / `coding_cli` 均只通过 `agent.sdk.kernel.submit` 注入 model，未直接操作 `agent.core`／`agent.platform` 内部。符合 AGENTS.md 依赖方向规则。
- **跨机/进程边界**：无新增跨机假设。model 传递链完全在进程内（Gateway 进程内持 kernel）。
- **复用 vs 平行**：model 注入利用既有 `loop.run` override 机制（`system_prompt_override` 同构），未另造机制。

### 代码模式一致性

- 注释密度、Google style docstring、`# bugfix-429` 溯源注释均沿用既有项目风格。
- `provider_of` / `_client_for_model` 命名符合既有 snake_case 约定。
- contract 白名单行号锚定更新（R2/R6 插行后 pin 已同步）。

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

无。

### SUGGESTION（可以修）

- `loop.py:97,189`：`self._model` 作为"迁移兜底 fallback"注释为 legacy，但实际上内核在 `build_kernel` 时仍将 `llm.model` 注入（`kernel.py:210`）。注释已说明这是兼容路径，如后续要完全清除内核对话默认的语义残留，可在下一个 unit 显式将 `self._model` 参数改为 `None`（仅清语义，不影响行为——所有真实调用方现均传 `model_override`）。不阻 PR。
  - **更正（bugfix-443）**：上句"所有真实调用方现均传 `model_override`"在 bugfix-429 收口时**不成立**——subagent 派发链（`agent.py` 后台/前台/resume 三派发点经 `subagent_runner`）与 `loop.py` 主动阈值压缩当时均未传 model，子 agent 及其侧链回退到内核构造期全局默认。已由 **bugfix-443** 补全（subagent 三派发点 + loop 主动压缩透传 per-run model）。

---

All checks passed. Ready for PR.
