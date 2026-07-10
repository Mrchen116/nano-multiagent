# refactor-372 M1 Triage Report

> 测量时间：2026-05-20
> 测量分支：`milestone/refactor-372-M1`（e2e 自动 marker + pytest-cov 已落地）
> 命令：`pytest -m "not e2e" -q --tb=line`

---

## 总览

| 指标 | 值 |
|---|---|
| 标记前基线（motivation.md） | 161 failed / 2018 passed |
| 实测基线（e2e marker 前） | 164 failed / 2015 passed |
| **加 e2e 自动 marker 后** | **145 failed / 1987 passed** |
| 标记修正移出的失败数 | 19（e2e 测试被正确过滤） |
| 残余失败数（待 M2 处理） | **145** |

### 四类计数

| 类别 | 计数 | 说明 |
|---|---|---|
| 过期预期（测试与现码漂移） | 128 | 产品主动演进，测试 mock / 断言没跟上 |
| 真回归（测试对，产品错） | 1 | 幂等 key 逻辑失效（已立 issue） |
| 一次性快照 | 3 | `tests/acceptance/` + importlib exec 反模式 |
| 环境干扰 | 1 | SOCKS 代理导致单测失败 |
| e2e 错分层（已通过 marker 修复） | 19 | 已由 R1 conftest hook 正确排除 |

> 注：e2e 错分层的 19 个失败在本次跑基线（e2e marker 后）已经不计入 145 内。

---

## 逐条清单

### 一、过期预期类（该改 — 测试对齐现码）

以下均为产品有意演进、测试 mock/断言未跟上。分子类列出。

#### 1.1 `create_app(auth_token=...)` 签名漂移（46 个失败）

产品 `agent.platform.http_api.app.create_app` 已去掉 `auth_token` 参数，但大量测试仍传该参数。

**M2 动作**：改测试，删 `auth_token=...` 调用（或改用当前 API 鉴权方式）。

涉及文件：
- `tests/contract/test_global_capabilities_contract.py`（2）
- `tests/contract/test_hook_intercept_contract.py`（1）
- `tests/contract/test_llm_config_contract.py`（3）
- `tests/contract/test_observability_contract.py`（1）
- `tests/contract/test_task_tool_contract.py`（通过但有依赖）
- `tests/contract/test_tools_contract.py`（通过但有依赖）
- `tests/integration/test_capabilities_wiring_integration.py`（1）
- `tests/integration/test_cli_async_retry_integration.py`（1）
- `tests/integration/test_cli_http_flow_integration.py`（27）
- `tests/integration/test_personal_assistant_server_integration.py`（6）
- `tests/unit/test_server_global_routes.py`（5）

#### 1.2 `ServerClient.send_message` 改名为 `submit_message`（1 个失败）

`tests/unit/test_sdk_client.py::test_send_message_posts_http_payload_with_auth_and_request_id`

证据：`AttributeError: 'ServerClient' object has no attribute 'send_message'`
产品：`src/coding_cli/client.py` 中方法为 `submit_message`。

**M2 动作**：更新测试，改调 `submit_message`，同时验证 HTTP payload 契约是否变化。

#### 1.3 `_FakeKernelClient.send_message_async` vs 产品 `submit_message`（5 个失败）

`tests/im_service/integration/test_m103_im_gateway_e2e.py`（5 个用例）

证据：`AttributeError: '_FakeKernelClient' object has no attribute 'submit_message'`
产品：`src/personal_assistant/gateway/inbound_pipeline.py:199` 调用 `kernel_client.submit_message(...)`
测试 mock `_FakeKernelClient` 只有 `send_message_async`（旧方法名）。

**M2 动作**：更新 `_FakeKernelClient`，将 `send_message_async` 改名/改签为 `submit_message`，对齐产品接口。

#### 1.4 `ManagedServerConfig.__init__()` 去掉了 `token` 参数（7 个失败）

`tests/unit/test_cli_managed_server.py`（7 个用例）

证据：`TypeError: ManagedServerConfig.__init__() got an unexpected keyword argument 'token'`

**M2 动作**：更新测试，不传 `token`，按当前 `ManagedServerConfig` 签名构造。

#### 1.5 `build_release_playbook_report()` 去掉了 `token` 参数（2 个失败）

`tests/unit/test_cli_refactor_boundaries.py::test_cli_release_playbook_is_thin_compat_shim`
`tests/unit/test_cli_refactor_boundaries.py::test_cli_release_playbook_execute_runs_steps_and_collects_status`

证据：`TypeError: build_release_playbook_report() got an unexpected keyword argument 'token'`

**M2 动作**：更新测试，不传 `token`。

#### 1.6 CLI commands 移除了 `test-token` / `create-session` / `send-message`（5 + 2 个失败）

测试期望 `test-token`、`create-session`、`send-message` 命令，但产品当前 CLI 只有 `health` 和 `llm-config`。

涉及：
- `tests/contract/test_cli_error_contract.py`（2）：`test-token` 命令不存在 → SystemExit 2
- `tests/contract/test_cli_http_only_contract.py::test_cli_exposes_minimal_http_commands`（1）
- `tests/unit/test_cli_refactor_boundaries.py::test_run_repl_passes_supported_commands_to_apps_input_reader`（1）

**M2 动作**：
- `test_cli_error_contract.py`：改用存在的命令测试错误 payload 格式；或删除（若错误 payload 已被其他测试覆盖）。
- `test_cli_http_only_contract.py::test_cli_exposes_minimal_http_commands`：断言更新为 `{"health", "llm-config"}` 子集。
- `test_cli_refactor_boundaries.py`：更新 `supported_commands` 期望值。

#### 1.7 `ToolSafetyConfig` 去掉了 bash 相关参数（2 个失败）

`tests/integration/test_tools_bash_integration.py`（2 个用例）

证据：`TypeError: ToolSafetyConfig.__init__() got an unexpected keyword argument 'bash_max_output_lines'`
M6 后 bash 相关配置移到 `BashRunnerConfig`，`ToolSafetyConfig` 只保留 read 限制。

**M2 动作**：更新测试，改用 `BashRunnerConfig` 或当前 `ToolSafetyConfig` 签名。

#### 1.8 契约字段漂移（3 个失败）

`tests/contract/test_core_types_contract.py::test_message_contract_fields_are_stable`
- 产品 `Message` 字段多了 `parent_message_id`、`group_id`；测试期望旧字段列表
- **M2 动作**：更新测试断言为当前 `Message` 字段列表（对齐现码，不删字段）

`tests/contract/test_core_types_contract.py::test_tool_contract_fields_are_stable`
- 产品 `ToolSpec` 多了 `max_result_size_chars`；测试期望旧字段列表
- **M2 动作**：更新测试断言

`tests/contract/test_llm_interfaces_contract.py::test_llm_generate_request_contract`
- 产品 `LLMGenerateRequest` 多了 `extra_body`；测试期望旧字段列表
- **M2 动作**：更新测试断言

#### 1.9 `core_no_platform_imports` 检测方法过粗（1 个失败）

`tests/contract/test_core_no_platform_imports.py::test_core_packages_do_not_import_platform_product_or_app_surfaces`

证据：`AssertionError: safety_types.py imports forbidden higher-level surface: agent.platform`
根因：测试做字符串全文搜索（含 docstring），`safety_types.py` 的 docstring 里有 `"now live in agent.platform.tools.builtins.bash_runner."` ——这是说明性文字，不是 import。文件本身没有 import `agent.platform`。

这是**测试逻辑的缺陷**，不是产品违反架构约束。

**M2 动作**：改测试，只扫 `import` 语句行（用正则匹配 `^from agent.platform` 或 `^import agent.platform`），不扫 docstring/注释。

#### 1.10 `messages:async` 路由 → `messages` 路由改名（4 个失败）

`tests/contract/test_runs_async_contract.py`（2）
`tests/contract/test_run_cancel_contract.py`（1）
`tests/integration/test_stop_command_integration.py`（1）

证据：`assert 404 == 202`；测试调 `/v1/sessions/{id}/messages:async`，产品当前路由为 `/v1/sessions/{id}/messages`（POST，返回 200）。

**M2 动作**：更新测试用的 URL 和期望的状态码（202 → 200）。

#### 1.11 `LLMGenerateRequest` 多了 `stream` 参数（2 个失败）

部分测试传了 `stream=True` 给 `LLMGenerateRequest`，现在该 dataclass 没有该字段。

**M2 动作**：更新测试，不传 `stream`（或按当前接口调整）。

#### 1.12 `KernelApiClient.stream_session` 丢失（1 个失败）

`tests/contract/test_personal_assistant_kernel_client_contract.py::test_kernel_api_client_exposes_gateway_http_subset`

证据：`AssertionError: assert False where False = hasattr(KernelApiClient, 'stream_session_events')`
产品 `KernelApiClient` 有 `stream_session` 方法；测试断言 `stream_session_events`（旧名）。

**M2 动作**：更新测试，检查 `stream_session` 而非 `stream_session_events`。

#### 1.13 `RunsRegistry` 异步 API 漂移（2 个失败）

`tests/contract/test_runs_async_contract.py::test_session_sse_run_status_contract_includes_retry_progress_fields`

证据：`AttributeError: module 'agent.core.runs.registry' has no attribute '_wait_with_cancel'`

**M2 动作**：更新测试，改用当前 `RunsRegistry` 公开 API。

#### 1.14 `RunController.run` 签名漂移（测试 mock 缺 `origin` 参数）（1 个失败）

`tests/unit/test_run_cancel.py::test_interrupt_signals_active_run_to_abort`

证据：`_AbortableBlockingRuntime.run()` 签名无 `origin` 参数，产品调 `runtime.run(..., origin=origin)`，TypeError 导致 run 立即 failed，interrupt 时已无 active run。

**M2 动作**：在测试 mock `_AbortableBlockingRuntime.run` 方法签名加 `origin=None`。

#### 1.15 `sync_message` 响应字段漂移（2 个失败）

`tests/contract/test_message_sync_contract.py`（2 个用例）

证据：`assert {'anchor_sequence',...} == {'completed',..., 'turn_id'}`；产品响应字段已改变。

**M2 动作**：更新契约断言，对齐当前 `POST /v1/sessions/{id}/messages` 响应 schema。

#### 1.16 `IM.conversations` auth 要求（6 个失败）

`tests/unit/IM/test_conversation_rename.py`（3 个用例）
`tests/unit/IM/test_messages_broadcast.py`（3 个用例）

证据：`assert 401 == 200/400/404/503`；测试未传 Authorization 头，但 IM API 的 conversations/messages endpoints 已要求 JWT 认证。

**M2 动作**：更新测试，在发请求前先调登录 endpoint 获取 token，或通过测试 fixture 注入认证 header。

#### 1.17 IM `relay_service.sender` 字段 `id` → `user_id`（6 个失败）

`tests/im_service/unit/test_relay_service.py`（6 个用例）

证据：`KeyError: 'id'`；产品 `_resolve_sender_info` 返回 `{"type": "user", "user_id": ..., "display_name": ...}`；测试断言 `sender["id"]`。

**M2 动作**：更新测试，用 `sender["user_id"]` 代替 `sender["id"]`；同样更新 `participants` 中的 `p["id"]` → `p["user_id"]`。

#### 1.18 `test_ws_event_types` token usage 字段漂移（1 个失败）

`tests/im_service/unit/test_ws_event_types.py::test_build_message_completed_payload_with_token_usage`

证据：`assert {'context_usage':{'total': 1042}} == {'context_usage':{'input': 1000, 'output': 42}}`

**M2 动作**：对齐当前 token usage 数据结构。

#### 1.19 `integration/test_cli_http_flow_integration.py` 大批漂移（27 个失败）

含 `auth_token`、`send-message`/`create-session` 命令不存在、async run API 变更等综合漂移。

**M2 动作**：逐个更新（见 1.1、1.10 对应条目），文件过大（1178 行）可在修完后考虑按行为拆分。

#### 1.20 bootstrap / capabilities / personal_assistant server 工具集漂移（12 个失败）

产品新增了 `skill_manage`、`task_stop`、`memory`、`agent` 工具，测试期望固定工具集（如 `{"bash", "edit", "write", "task"}`）。

`tests/integration/test_bootstrap_integration.py`（1）
`tests/integration/test_personal_assistant_bootstrap_integration.py`（2）
`tests/integration/test_personal_assistant_server_integration.py`（6）
`tests/unit/test_app_factory_with_profile.py`（1）
`tests/im_service/integration/test_agent_config_api.py`（2）

**M2 动作**：更新断言，检查新工具集中是否包含特定工具（用 `issubset` 或 `assertIn`），而非等号断言固定集合。

#### 1.21 IM service integration 测试（剩余漂移）

`tests/im_service/integration/test_chat_flow_integration.py`（1）
`tests/im_service/integration/test_create_agent_flow.py`（1）
`tests/im_service/integration/test_messages_api.py`（2）
`tests/im_service/integration/test_users_conversations_api.py`（1）
`tests/im_service/integration/test_m136_group_chat_flow.py`（3）

证据混合：`assert 0 == 2`、`KeyError: 'id'`、断言字段不匹配。

**M2 动作**：按错误逐条调查，属于 IM service schema/行为漂移，对齐现码。

#### 1.22 `tests/integration/test_anthropic_generation_integration.py` 等 LLM adapter 漂移（2 个失败）

产品 `LLMGenerateRequest` 字段变化影响 Anthropic / OpenAI compat adapter 测试。

**M2 动作**：对齐新 `LLMGenerateRequest` 字段。

#### 1.23 `tests/integration/test_task_*` 工具/API 漂移（5 个失败）

`test_task_blocking_integration.py`（1）、`test_task_non_blocking_integration.py`（2）、`test_task_skills_integration.py`（3）

证据混合，主因是 create_app auth_token + task 工具名称漂移。

**M2 动作**：同 1.1 + 1.20。

#### 1.24 `tests/integration/test_tools_registry_loader_integration.py`（2 个失败）

`tests/integration/test_tools_read_integration.py`（5 个失败）

主因是 `ToolSafetyConfig` 签名漂移（见 1.7）。

**M2 动作**：同 1.7。

#### 1.25 `tests/integration/test_m8_agent_tool_hook_r81_integration.py`（5 个失败）

证据：`hook_integration_contract` 同款问题（`ToolContext.create` 依赖 safety config factory 未配置）。

**M2 动作**：在测试 setup 里配置 `tool_safety_config_factory`，或用 `ToolSafetyConfig()` 直接传入。

---

### 二、真回归类（测试对，产品错 — 已立 issue）

#### 2.1 幂等 key（idempotency_key）无效 — `append_message` 接口不幂等

`tests/integration/test_session_flow_integration.py::test_append_message_persists_history_once_per_idempotency_key`

**现象**：两次携带相同 `idempotency_key` 的 `POST /v1/sessions/{id}/messages:append` 返回了不同 `entry_id`，说明第二次没有走 dedup 路径，而是创建了新 entry。

**验证**：
```python
r1 = client.post(f'/v1/sessions/{sid}/messages:append', json={..., 'idempotency_key': 'key-1'})
r2 = client.post(f'/v1/sessions/{sid}/messages:append', json={..., 'idempotency_key': 'key-1'})
assert r1.json()['entry_id'] != r2.json()['entry_id']  # 实测确认
```

**根因**：`agent.platform.persistence.session.service.SessionService.append_message` 里存在幂等查找逻辑（`_find_message_by_idempotency_key`），但实测失败，可能原因是 `TestClient` 每次请求创建新的 `SessionService` 实例（状态未共享）。

**M2 动作**：⚠️ 已立 issue（见下），用 `@pytest.mark.xfail(reason="...; tracked in #<N>", strict=True)` 标记。

---

### 三、一次性快照类（该删）

#### 3.1 `tests/acceptance/test_im_gateway_real_acceptance.py`（2 个失败）

需要真实运行的 IM + Gateway 服务，在本地没有服务时全部返回 404。

**判定**：这是一次性端到端验收脚本（单次用来验收 milestone 功能），没有长期回归价值（问自己"半年后每次 CI 都要跑吗" → 否）。

**M2 动作**：删除整个文件（2 个用例），将 `ACCEPTANCE/` 目录里对应的 milestone 脚本标注为"已验收，不入套件"。

#### 3.2 `tests/unit/test_rerun_acceptance_runtime_helpers.py`（当前通过，但属于反模式）

用 `importlib.util.exec_module` 把 `ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py` 当被测模块导入。这是 TESTING_GUIDE §6 明确禁止的反模式：一次性验收脚本不应进套件，更不该用 exec 方式当成 src 代码测试。

**当前状态**：测试通过（因为 `ACCEPTANCE/` 目录存在），但是 fragile：如果 ACCEPTANCE 脚本被清理就会炸收集。

**M2 动作**：删除整个文件（659 行），同时确认 `ACCEPTANCE/m170-runtime/` 里的运行时助手逻辑如有真正的回归价值应提进 `src/`。

---

### 四、环境干扰类

#### 4.1 SOCKS 代理导致 `test_kernel_api_client_requires_token_for_authenticated_calls` 失败

`tests/unit/personal_assistant/test_kernel_api_client.py::test_kernel_api_client_requires_token_for_authenticated_calls`

证据：`ImportError: Using SOCKS proxy, but the 'socksio' package is not installed.`

**根因**：测试环境存在 SOCKS 代理配置（`HTTPS_PROXY`/`ALL_PROXY` 环境变量），httpx 尝试使用 SOCKS 但没装 `socksio`。与产品代码无关。

**M2 动作**：在该测试（或 conftest）里添加 `monkeypatch.delenv("HTTPS_PROXY", raising=False)` / `monkeypatch.delenv("ALL_PROXY", raising=False)` 清除代理环境变量；或 `pip install socksio` 进 dev 依赖。

---

## 结构问题盘点

### S1 流水号命名文件（违反 TESTING_GUIDE §3）

以下文件用 milestone 编号命名，半年后无人能解读：

| 文件 | 行数 | 建议 |
|---|---|---|
| `tests/contract/test_m85_canonical_wiring_imports.py` | 小 | M2 重命名为行为描述名 |
| `tests/contract/test_m86_canonical_homing_imports.py` | 小 | M2 重命名 |
| `tests/e2e/test_m112_real_process_roundtrip_e2e.py` | 1164 | M2 重命名（如 `test_gateway_process_integration_e2e.py`）+ 可考虑拆分 |
| `tests/im_service/integration/test_m103_im_gateway_e2e.py` | 1419 | M2 重命名（如 `test_gateway_im_pipeline_integration.py`）+ 拆分 |
| `tests/unit/test_m236_session_metadata_hookcontext.py` | 中 | M2 重命名 |
| `tests/unit/test_m170_runtime.py` | 中 | M2 重命名 |
| `tests/unit/test_refactor353_corrigendum.py` | 小 | M2 重命名或合并 |
| `tests/unit/test_rerun_acceptance_runtime_helpers.py` | 659 | M2 删除（见 3.2） |
| `tests/unit/personal_assistant/test_m102_gateway_im_connection.py` | 866 | M2 重命名 + 可考虑拆分 |

### S2 超过 400 行的测试文件（违反 TESTING_GUIDE §7）

| 文件 | 行数 | 优先级 |
|---|---|---|
| `tests/unit/test_cli_main.py` | 2754 | 高（最大） |
| `tests/unit/personal_assistant/test_main.py` | 2120 | 高 |
| `tests/unit/personal_assistant/test_gateway_pipeline.py` | 1676 | 高 |
| `tests/im_service/integration/test_m103_im_gateway_e2e.py` | 1419 | 高（同时需重命名） |
| `tests/integration/test_cli_http_flow_integration.py` | 1178 | 高 |
| `tests/e2e/test_m112_real_process_roundtrip_e2e.py` | 1164 | 中（e2e，单独处理） |
| `tests/unit/test_tools_builtins.py` | 923 | 中 |
| `tests/unit/personal_assistant/test_m102_gateway_im_connection.py` | 866 | 中（同时需重命名） |
| `tests/unit/test_background_hook_fork.py` | 843 | 中 |
| `tests/im_service/unit/test_repositories.py` | 790 | 中 |
| `tests/e2e/test_personal_assistant_main_e2e.py` | 765 | 中（e2e，单独处理） |
| `tests/unit/test_agent_loop.py` | 723 | 中 |
| `tests/unit/test_auto_mode_gate.py` | 698 | 中 |
| `tests/im_service/integration/test_m136_group_chat_flow.py` | 697 | 中 |
| `tests/unit/test_rerun_acceptance_runtime_helpers.py` | 659 | 低（删除即可，见 3.2） |
| `tests/im_service/unit/test_relay_service.py` | 627 | 中 |
| `tests/unit/personal_assistant/test_local_store.py` | 619 | 中 |

### S3 一次性快照混入套件

| 路径 | 性质 | M2 动作 |
|---|---|---|
| `tests/acceptance/test_im_gateway_real_acceptance.py` | 需真实服务的一次性验收 | 删除 |
| `tests/unit/test_rerun_acceptance_runtime_helpers.py` | importlib exec 一次性脚本（TESTING_GUIDE §6 反模式） | 删除 |

### S4 跨层重复疑似对（需 M2 核查）

| 对 | 性质 |
|---|---|
| `test_m102_gateway_im_connection.py`（unit/PA） + `test_m103_im_gateway_e2e.py`（im_service/integration） | 都测 Gateway ↔ IM 集成，用不同 mock 深度；M2 确认是否有大量重叠断言可去重 |
| `test_hook_integration_contract.py`（contract） + `test_m8_agent_tool_hook_r81_integration.py`（integration） | 都测 hook 管道；M2 检查是否有重复断言 |

---

## 已立 issue

| issue | 标题 | 对应测试 |
|---|---|---|
| #37 | `append_message` 幂等 key 无效：同一 idempotency_key 返回不同 entry_id | `test_append_message_persists_history_once_per_idempotency_key` |

---

## M2 范围建议

基于本 triage 报告，M2 的执行工作约可分为以下几组（设计 author 在 Changelog 里定稿）：

1. **批量 API 签名漂移修复**（估计占 80+ 用例）：`create_app` 无 `auth_token`、`send_message`→`submit_message`、token 参数移除、`messages:async`→`messages` 路由
2. **契约字段更新**（~10 用例）：Message / ToolSpec / LLMGenerateRequest 字段列表、sender 字段 `id`→`user_id`
3. **工具集断言改写**（~12 用例）：固定集合 → subset 断言
4. **IM 认证 fixture**（~6 用例）：conversation rename + messages broadcast 加 auth
5. **删除一次性快照**（~3 用例 + 大文件）：acceptance 目录 + rerun_acceptance
6. **文件重命名 + 拆分**（优先级低）：流水号命名 + 超 400 行文件
7. **真回归处理**：幂等 key issue 修复后移除 xfail 标记

M2 体量大，设计 author 可考虑拆分为并行工作流（如按上述 1-4 分组派给不同 worker）。
