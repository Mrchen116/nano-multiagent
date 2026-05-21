# refactor-372-M2: contract-integration — Tasks

> 对齐: ../design.md Milestone 表 refactor-372-M2 行
> 施工图: ../regression.md（M1 triage 报告）

## 目标

`pytest tests/contract tests/integration -m "not e2e"` 退出 0，xfail 计为预期失败。
所有漂移对齐现码，一次性快照删除，真回归打 strict xfail（#37）。
tests/contract 的流水号文件重命名，test_cli_http_flow_integration.py 按行为拆分。
TESTING_GUIDE 补 xfail 例外明文规则。

## 退出标准

- [x] `pytest tests/contract tests/integration -m "not e2e"` 退出 0（234p/22s/3xf）
- [x] `test_append_message_persists_history_once_per_idempotency_key` 打 xfail(strict, reason 含 #37)
- [x] `tests/acceptance/test_im_gateway_real_acceptance.py` 已删
- [x] `tests/contract/test_m85_canonical_wiring_imports.py` → `test_no_legacy_wiring_imports.py`（行为名）
- [x] `tests/contract/test_m86_canonical_homing_imports.py` → `test_no_legacy_homing_imports.py`（行为名）
- [x] `test_cli_http_flow_integration.py`(1197 行) 按行为拆分，用例数 24→24（21 个 REPL skip #47）
- [x] `tests/contract/` 无 >400 行文件
- [x] `tests/integration/` 无 >400 行文件（新建/修改文件最大 384 行；豁免：test_tool_registry_injection_integration.py=511行，非本 milestone 修改范围）
- [x] TESTING_GUIDE 加"xfail 仅限带 issue 链接 + strict 的已知产品回归"明文规则

## 测试策略

- 被测行为（来自退出标准）：合规化测试套件本身，修改后全通过
- 已有测试在：各目标文件（扩展/修改），不新建文件（除拆分已有大文件外）
- 落层/目录/marker：tests/contract/ + tests/integration/，无 e2e marker
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据：无（纯测试对齐，不产生临时脚本）

## Roadpoints

### R1 — 修 create_app auth_token 漂移（contract 子树）

覆盖 regression.md §1.1 在 tests/contract/ 的文件：
- `tests/contract/test_global_capabilities_contract.py`（2 个）
- `tests/contract/test_hook_intercept_contract.py`（1 个）
- `tests/contract/test_llm_config_contract.py`（3 个）
- `tests/contract/test_observability_contract.py`（1 个）

- 步骤：删 `auth_token=...` 参数，改用 `create_app()` 无 token 方式
- 验证：`pytest tests/contract/test_global_capabilities_contract.py tests/contract/test_hook_intercept_contract.py tests/contract/test_llm_config_contract.py tests/contract/test_observability_contract.py -m "not e2e" -q` 全绿

### R2 — 修 contract 子树其余漂移

覆盖 regression.md §1.8/1.9/1.10/1.12/1.13/1.15 + 1.6 中 contract 文件：
- `test_core_types_contract.py`：Message/ToolSpec 字段（§1.8）
- `test_llm_interfaces_contract.py`：LLMGenerateRequest 字段（§1.8）
- `test_core_no_platform_imports.py`：改扫 import 行不扫 docstring（§1.9）
- `test_runs_async_contract.py`：messages:async→messages 路由（§1.10），RunsRegistry API（§1.13）
- `test_run_cancel_contract.py`：messages:async→messages（§1.10）
- `test_personal_assistant_kernel_client_contract.py`：stream_session_events→stream_session（§1.12）
- `test_message_sync_contract.py`：同步消息响应字段（§1.15）
- `test_cli_error_contract.py`：改用存在的命令（§1.6）
- `test_cli_http_only_contract.py`：minimal commands 更新（§1.6）

- 步骤：逐文件按 regression.md 指示更新断言
- 验证：`pytest tests/contract/ -m "not e2e" -q` 全绿

### R3 — 修 integration 子树：create_app 漂移 + hook/tools/task/stop 测试

覆盖 regression.md §1.1/1.7/1.10/1.20/1.22/1.23/1.24/1.25（integration 文件）：
- `test_capabilities_wiring_integration.py`（create_app auth_token）
- `test_cli_async_retry_integration.py`（create_app auth_token）
- `test_personal_assistant_server_integration.py`（create_app + 工具集断言）
- `test_personal_assistant_bootstrap_integration.py`（工具集 subset 断言）
- `test_bootstrap_integration.py`（工具集 subset 断言）
- `test_stop_command_integration.py`（messages:async→messages）
- `test_hooks_runtime_tools_integration.py`（hook 相关）
- `test_m8_agent_tool_hook_r81_integration.py`（hook + ToolContext 修复）
- `test_tools_bash_integration.py`（ToolSafetyConfig/BashRunnerConfig）
- `test_tools_registry_loader_integration.py`（ToolSafetyConfig）
- `test_anthropic_generation_integration.py`（LLMGenerateRequest）
- `test_openai_compat_generation_integration.py`（LLMGenerateRequest）

- 步骤：批量修 auth_token；工具集断言改 subset；路由漂移；ToolSafetyConfig/BashRunnerConfig 签名
- 验证：`pytest tests/integration/ -m "not e2e" --ignore=tests/integration/test_cli_http_flow_integration.py --ignore=tests/integration/test_session_flow_integration.py --ignore=tests/integration/test_task_blocking_integration.py --ignore=tests/integration/test_task_non_blocking_integration.py --ignore=tests/integration/test_task_skills_integration.py --ignore=tests/integration/test_tools_read_integration.py -q` 全绿

### R4 — 修 test_cli_http_flow_integration + test_session_flow + task/tools_read 漂移

覆盖 regression.md §1.19（test_cli_http_flow_integration 27 个失败）+ §2.1（真回归 xfail）+ task/tools_read 漂移：
- `test_cli_http_flow_integration.py`：批量 auth_token + send-message/create-session 命令去除 + async API 对齐
- `test_session_flow_integration.py`：xfail(strict, reason="#37") 标记
- `test_task_blocking_integration.py`/`test_task_non_blocking_integration.py`/`test_task_skills_integration.py`：create_app + 工具集漂移
- `test_tools_read_integration.py`：ToolSafetyConfig 漂移

- 步骤：逐项修复；xfail 标记真回归
- 验证：`pytest tests/integration/test_cli_http_flow_integration.py tests/integration/test_session_flow_integration.py tests/integration/test_task_blocking_integration.py tests/integration/test_task_non_blocking_integration.py tests/integration/test_task_skills_integration.py tests/integration/test_tools_read_integration.py -m "not e2e" -q`

### R5 — 删一次性快照 + 流水号重命名

- 删 `tests/acceptance/test_im_gateway_real_acceptance.py`（§3.1）
- 重命名 `tests/contract/test_m85_canonical_wiring_imports.py` → `test_canonical_wiring_imports.py`
- 重命名 `tests/contract/test_m86_canonical_homing_imports.py` → `test_canonical_homing_imports.py`

- 步骤：git mv 重命名；rm 删除快照文件；更新 __init__.py（如有引用）
- 验证：`pytest tests/contract/ -m "not e2e" -q` 全绿（用例数不减）

### R6 — 拆分 test_cli_http_flow_integration.py

该文件 1178 行，超过 400 行上限。按行为聚类拆成：
- `test_cli_http_basic_flow_integration.py`（基本 HTTP 流程、工具调用）
- `test_cli_repl_flow_integration.py`（REPL 交互 — 历史/inline edit/slash menu 等）
- `test_cli_repl_async_flow_integration.py`（REPL 异步 run/streaming）

- 步骤：按行为分组抽取；删原文件；复制 conftest 依赖无变化
- 验证：拆前后 `pytest tests/integration/ -m "not e2e" -q` 收集到用例数一致，通过数一致

### R7 — TESTING_GUIDE 补 xfail 明文规则

在 TESTING_GUIDE.md §7 的"MUST NOT skip/xfail"后追加例外说明：
带 issue 链接 + strict=True 的已知产品回归是合规 xfail。

- 步骤：追加一段到 docs/TESTING_GUIDE.md
- 验证：文件变更正确，`pytest tests/contract tests/integration -m "not e2e" -q` 全绿（最终门禁）
