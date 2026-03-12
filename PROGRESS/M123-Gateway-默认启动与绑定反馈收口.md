# M123 Gateway 默认启动与绑定反馈收口

## 启动记录
- 已阅读：`LOGBOOK.md`、`COMMENTING_GUIDE.md`、`/Users/czj/.codex/skills/tdd-execution-worker/SKILL.md`。
- 注释规范承诺：新增 public module/class/function/method 使用 Google 风格 docstring；注释只解释意图、边界、代价。
- 当前处境：M123，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M123`，branch=`milestone/M123`。
- 测试门禁：`PYTHONPATH=src pytest -q tests/acceptance/test_im_gateway_real_acceptance.py tests/e2e/test_m112_real_process_roundtrip_e2e.py tests/im_service/integration/test_gateway_websocket_api.py tests/unit/personal_assistant`。
- 基线结果：
  - 当前环境首轮结果为 `56 passed / 7 failed`
  - 失败全部来自 `tests/e2e/test_m112_real_process_roundtrip_e2e.py` 的 `_pick_free_port()`，错误为 `PermissionError: [Errno 1] Operation not permitted`
  - 判断：这是 sandbox 禁止本地端口绑定的环境限制，不是 M123 scope 内业务失败；后续以 M123 定向测试的红绿变化为主
- 关键排查线索：
  - `/Users/czj/Repos/nano-multiagent/node-config.yaml` 默认 `node.node_id=my-macbook`、`im_service.url=http://127.0.0.1:8021`
  - `ACCEPTANCE/M120-acceptance.md` 记录真实失败为 `ERROR node my-macbook did not appear in IM bootstrap` 与 `ValueError: missing API token for kernel client`
  - 当前代码里 `_IMBootstrapClient.ensure_node_binding()` 只会在节点不可见时抛 `RuntimeError("node ... did not appear in IM bootstrap")`，`KernelApiClient` 在 require_auth=True 且 token 为空时直接抛 `ValueError("missing API token for kernel client")`

### R1 默认启动路径与 kernel 认证对齐
- Context:
  - 默认 `node-config.yaml` 未声明 `kernel.token`，但 agent HTTP `/v1/sessions`、`/v1/runs/*` 路由仍要求 bearer header，导致正常本地 Gateway 首次处理消息时抛 `missing API token for kernel client`。
  - 该断点不应暴露给默认用户路径；即使用户没显式配置 token，本地 managed kernel 也应该与 Gateway 默认协同。
- Decision:
  - 在 `local_store.py` 新增 `DEFAULT_LOCAL_KERNEL_TOKEN` 与 `resolve_kernel_token()`：优先用显式 `kernel.token`，其次复用环境变量 `NANO_MULTIAGENT_API_TOKEN`，最后回退到稳定本地默认 token。
  - 在 `_parse_kernel()` 与 `build_runtime()` 都使用该解析逻辑，避免 YAML 加载路径与手工构造 `LocalConfig` 路径出现 token 漏传。
- Rationale:
  - agent HTTP 服务在未设置固定 `auth_token` 时依然要求 bearer header 存在，因此 Gateway 需要“默认带 token”而不是把缺失 token 变成用户心智负担。
  - 双层收口能覆盖真实默认入口与测试/手工构造配置两条路径，避免只修 YAML happy path。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/personal_assistant/test_local_store.py::test_load_local_config_defaults_kernel_token_for_local_gateway tests/unit/personal_assistant/test_main.py::test_build_runtime_defaults_local_kernel_token_when_config_omits_it` -> `2 passed`
  - Tests: `PYTHONPATH=src pytest -q tests/acceptance/test_im_gateway_real_acceptance.py tests/e2e/test_m112_real_process_roundtrip_e2e.py tests/im_service/integration/test_gateway_websocket_api.py tests/unit/personal_assistant` -> 仅保留既有 7 个 sandbox 端口绑定失败，无新增回归
  - Entry: 默认本地配置省略 `kernel.token` 时，Gateway runtime 构造出的 `KernelApiClient` 已携带稳定 bearer token，不再在首次 authenticated kernel call 前直接因 token 缺失中断。
- Rollback: 67bc6c6b601c9270e319551b55df59b2850d5d8f
- Commits: C1=67bc6c6, C2=29fe2bf, C3=8b6e35d
- Next: 进入 R2，处理 IM bootstrap 节点不可见、未绑定提示与用户可执行反馈。

### R2 节点可见性与未绑定反馈
- Context:
  - 真实失败里 `_IMBootstrapClient` 只会输出 `node ... did not appear in IM bootstrap`，既没有告诉用户该检查哪个入口，也没有把失败回写到 IM 节点状态。
  - 默认 `im_service.url` 可能指向本地代理入口；若 websocket 已接通但 `/im/v1/nodes` 不在同一端口，用户不应自己推理 8011/8021 等细节。
  - 未绑定成功时虽然会尝试开浏览器，但后台默认启动路径缺少显式 `NEXT ...` 输出，用户很容易错过 bind URL。
- Decision:
  - 新增 `GatewayStartupError(summary, next_step)` 作为统一启动失败语义，`main()` 直接打印 `ERROR ...` + `NEXT ...`，后台模式也会落到 `gateway.log`。
  - `_IMBootstrapClient` 新增本地 IM API base 回退逻辑：对 loopback 配置先查当前 `im_service.url`，若节点列表未找到节点，再回退到 `http://127.0.0.1:8011` 的同路径，减少本地代理/真实 API 端口错配导致的“节点不可见”断点。
  - 未绑定成功创建 bind URL 后，统一输出 `ACTION ...` + `NEXT Open <bind_url> ...`；若 bootstrap 最终失败，`GatewayRuntime` 会在退出前通过 `node.heartbeat` 把 `last_error` 写回 IM 节点板，使 `/im/v1/nodes` 可见下一步。
- Rationale:
  - 该方案不改前端路由、不扩新 HTTP 文档入口，只在 Gateway/IM 现有默认路径内把“节点没出现 / 未绑定 / 下一步是什么”显式化。
  - 通过重用现有 `node.heartbeat.last_error`，反馈可直接出现在真实 IM 节点列表，不需要增加新 API 面。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/personal_assistant/test_main.py::test_im_bootstrap_client_falls_back_to_local_im_api_port_when_primary_bootstrap_host_has_no_node tests/unit/personal_assistant/test_main.py::test_gateway_runtime_reports_actionable_bootstrap_failure_to_im tests/unit/personal_assistant/test_main.py::test_main_surfaces_next_step_for_gateway_startup_error tests/im_service/integration/test_gateway_websocket_api.py::test_gateway_websocket_exposes_actionable_last_error_in_node_board` -> `4 passed`
  - Tests: `PYTHONPATH=src pytest -q tests/acceptance/test_im_gateway_real_acceptance.py tests/im_service/integration/test_gateway_websocket_api.py tests/unit/personal_assistant` -> `61 passed`
  - Tests: `PYTHONPATH=src pytest -q tests/acceptance/test_im_gateway_real_acceptance.py tests/e2e/test_m112_real_process_roundtrip_e2e.py tests/im_service/integration/test_gateway_websocket_api.py tests/unit/personal_assistant` -> 仅保留既有 7 个 sandbox 端口绑定失败，无新增回归
  - Entry: 背景/前台 Gateway 启动在 bind required 或 bootstrap failure 时都会输出 `NEXT ...`；若 bootstrap 失败，IM `/im/v1/nodes` 可见 `last_error`，用户可直接从节点板看到下一步。
- Rollback: a565d427313f55849f2c3cb6e3f46373ff40f5f9
- Commits: C1=a565d42, C2=ded78e4, C3=<pending>
- Next: 进入里程碑集成、rebase、main 合并与 dev_tasks 更新。
