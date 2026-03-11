# M98 Gateway 骨架 + 配置 + 内核客户端

## 启动记录
- 已阅读：`SPEC.md`、`docs/NodeGateway-SPEC.md`、`docs/内核设计SPEC.md`、`LOGBOOK.md`、`ROADMAP.md`、`COMMENTING_GUIDE.md`。
- 注释规范承诺：后续新增 public module/class/function/method 均按 Google 风格 docstring 写契约；注释只解释意图、边界、代价，不复述代码。
- 当前处境：M98，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M98`，branch=`milestone/M98`。
- 测试门禁：`PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M98/src pytest -q`。
- 基线结果：开始前全量 pytest 失败 1 条，失败点为 `tests/contract/test_multi_product_architecture_acceptance.py::test_architecture_docs_describe_zero_residue_target_state` 读取旧 agent 线程私有路径下的 `多产品架构调整建议.md`，与 M98 scope 无关；M98 在该基线上继续执行，但需确保不新增失败。
- prevention / 注意事项：
  - 严守 NodeGateway-SPEC §15：`personal_assistant` 不得直接 import `agent` 内部模块，所有内核交互通过 HTTP client。
  - 仅实现 M98 所需骨架、配置、client、入口生命周期；不提前落地 M100+ 的 channel / queue / ws / scheduler 实现。
  - worktree 内 `data/dev-tasks.json` 已链接到主仓共享文件，避免状态分叉。

### R1 包骨架与配置加载
- Context: M98 先要补齐 `src/personal_assistant/` 顶层占位，并提供 NodeGateway-SPEC §11 所需的最小本地配置读取能力；当前仓库未包含该包，也未声明包发现。
- Decision: 新建 `personal_assistant` 包与 `config/local_store.py`，用 dataclass + YAML 解析实现只读配置模型；对 node/agents/channels/kernel/im_service 建立最小强校验，并在 `pyproject.toml` 中加入 `personal_assistant*` 包发现。
- Rationale: dataclass 足够覆盖当前骨架阶段的静态配置需求，依赖面小，后续可平滑扩展到更多 gateway 子模块；强校验可提前阻断不存在的 workspace 等运维错误。
- Evidence:
  - Tests: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M98/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M98/tests/unit/personal_assistant/test_local_store.py /Users/czj/Repos/nano-multiagent/.worktrees/M98/tests/contract/test_personal_assistant_package_contract.py`；`PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M98/src pytest -q`（仅保留既有基线失败 `test_architecture_docs_describe_zero_residue_target_state`）
  - Entry: `load_local_config()` 可从 `node-config.yaml` 读取 node/agents/channels/kernel 配置并回填默认 kernel 探活参数。
- Rollback: 235c324cf537411ea94c78f1568f76fd4b8804bb
- Commits: C1=235c324, C2=
- Next: 进入 R2，补 agent HTTP 子集客户端与 SSE 解析。

### R2 内核 HTTP 客户端
- Context: NodeGateway-SPEC §9 要求 Gateway 只通过 HTTP 调用 agent 内核的 health/sessions/messages:async/events/runs/cancel 子集；仓库虽已有 SDK client，但 M98 需要 personal_assistant 自己的最小边界与契约测试。
- Decision: 新增 `client/kernel_api_client.py`，提供 `KernelApiClientConfig` 与 6 个子集方法；统一注入 bearer token / request id / timeout，错误响应映射为带 `code/message/trace_id` 的 `RuntimeError`，并内置 SSE 文本解析。
- Rationale: 保持 personal_assistant 边界最小而明确，避免直接复用 CLI/SDK 更宽的接口集；同时保留和现有 server HTTP 契约一致的请求/响应语义。
- Evidence:
  - Tests: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M98/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M98/tests/unit/personal_assistant/test_kernel_api_client.py /Users/czj/Repos/nano-multiagent/.worktrees/M98/tests/contract/test_personal_assistant_kernel_client_contract.py`；`PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M98/src pytest -q`（仅保留既有基线失败 `test_architecture_docs_describe_zero_residue_target_state`）
  - Entry: `KernelApiClient` 已能用 `httpx.MockTransport` 打通 create_session → messages:async → get_run/cancel_run，并把 `/events` SSE 解析为结构化列表。
- Rollback: b44e41296d372f590ad53d29fa6f05577ef979fe
- Commits: C1=b44e412, C2=
- Next: 进入 R3，补 main.py 生命周期编排与最小入口 e2e。

### R3 进程入口与内核子进程生命周期
- Context: M98 需要 `main.py` 证明 Gateway 能加载配置、启动 agent 内核子进程、轮询 `/v1/health`，并在退出时执行 terminate→kill；但不能提前落地 M100+ 的 channel / scheduler 常驻行为。
- Decision: 新增 `personal_assistant.main`，拆成 `GatewayProcessManager`（子进程与探活）、`GatewayRuntime`（最小运行骨架）、`run_gateway()` / `main()`（入口）；通过可注入 factories/process_factory/clock 让生命周期逻辑可单测和 e2e 验证。
- Rationale: 先把进程管理和配置接线做成可替换边界，既满足 M98 骨架验收，也为后续 M100+ 扩展留出稳定插槽；测试中无需真实长驻服务即可覆盖 terminate→kill 分支。
- Evidence:
  - Tests: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M98/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M98/tests/unit/personal_assistant /Users/czj/Repos/nano-multiagent/.worktrees/M98/tests/contract/test_personal_assistant_package_contract.py /Users/czj/Repos/nano-multiagent/.worktrees/M98/tests/contract/test_personal_assistant_kernel_client_contract.py /Users/czj/Repos/nano-multiagent/.worktrees/M98/tests/contract/test_personal_assistant_main_contract.py /Users/czj/Repos/nano-multiagent/.worktrees/M98/tests/e2e/test_personal_assistant_main_e2e.py`；`PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M98/src pytest -q`（仅保留既有基线失败 `test_architecture_docs_describe_zero_residue_target_state`）
  - Entry: `run_gateway()` 已能从 YAML 加载配置，构造 runtime，并在 fake kernel client/process 下验证健康轮询与 terminate→kill 关闭序列。
- Rollback: f109c97f01f0f3d6a285f4dce4451c070b6c36dc
- Commits: C1=f109c97, C2=
- Next: Milestone 代码已达 M98 scope，进入收尾文档提交与集成。
