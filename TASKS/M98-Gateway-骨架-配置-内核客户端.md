# M98 Gateway 骨架 + 配置 + 内核客户端

## 前置确认
- 已先阅读 `SPEC.md`、`docs/NodeGateway-SPEC.md`、`docs/内核设计SPEC.md`、`LOGBOOK.md`、`ROADMAP.md`、`COMMENTING_GUIDE.md`。
- 本 Milestone 的代码与文档将遵守 `COMMENTING_GUIDE.md` 的 public API docstring / 注释规范。
- 参考 LOGBOOK：本次仅在 `src/personal_assistant/` 与对应测试/文档内收口，不扩散到其它 milestone 范围；基线门禁当前存在与 M98 无关的既有失败，见 PROGRESS 记录。

## 当前处境
- Milestone: M98 / Gateway 骨架 + 配置 + 内核客户端
- execution_mode: parallel
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M98`
- branch: `milestone/M98`
- 测试门禁命令: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M98/src pytest -q`
- 允许改动范围: `src/personal_assistant/`、相关测试、`pyproject.toml` 包发现配置、`TASKS/`、`PROGRESS/`，以及为 M98 必要的最小接线
- 禁止改动范围: `src/IM/`、未被 M98 要求的 gateway/channel/scheduler/ws/reporter 未来能力、其它 milestone 文档与实现

## Roadpoints

### R1 包骨架与配置加载
- Status: DONE
- Acceptance:
  - `src/personal_assistant/` 作为独立 Python 包存在，含 `__init__.py`
  - `config/local_store.py` 可从 YAML 文件加载 Gateway 本地配置
  - 配置模型覆盖 NodeGateway-SPEC §11 的最小字段：node / agents / channels / im_service / kernel
  - public API docstring 符合 COMMENTING_GUIDE
  - 包发现配置包含 `personal_assistant*`
- Tests Plan:
  - unit: 需要，验证 YAML 解析、默认值、路径校验、缺失字段报错
  - contract: 需要，验证包存在与包发现配置包含 `personal_assistant*`
  - integration: 不选，本 Roadpoint 无跨模块链路
  - e2e: 不选，本 Roadpoint 不涉及真实入口
- Expected Tests:
  - `tests/unit/personal_assistant/test_local_store.py`
  - `tests/contract/test_personal_assistant_package_contract.py`
- DoD:
  - `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M98/src pytest -q` 除既有基线失败外无新增失败，且 M98 定向测试全绿
  - 完成 C1/C2/C3
  - PROGRESS 写清配置结构、默认值与证据

### R2 内核 HTTP 客户端
- Status: TODO
- Acceptance:
  - `client/kernel_api_client.py` 存在并封装 `/v1/health`、`/v1/sessions`、`/v1/sessions/{id}/messages:async`、`/v1/sessions/{id}/events`、`/v1/runs/{id}`、`/v1/runs/{id}/cancel`
  - 支持 bearer token、request id、timeout 配置
  - SSE 轮询结果可解析为结构化事件
  - 错误响应统一映射为可诊断异常
  - 不直接 import `agent` 内部模块，只走 HTTP
- Tests Plan:
  - unit: 需要，验证参数校验、headers、SSE 解析、错误映射
  - contract: 需要，验证方法名与最小 API 子集
  - integration: 需要，使用 `httpx.MockTransport` 贯通请求/响应
  - e2e: 不选，本 Roadpoint 不需要启动真实进程
- Expected Tests:
  - `tests/unit/personal_assistant/test_kernel_api_client.py`
  - `tests/contract/test_personal_assistant_kernel_client_contract.py`
- DoD:
  - `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M98/src pytest -q` 除既有基线失败外无新增失败，且 M98 定向测试全绿
  - 完成 C1/C2/C3
  - PROGRESS 写清 HTTP 边界与错误语义

### R3 进程入口与内核子进程生命周期
- Status: TODO
- Acceptance:
  - `main.py` 作为 Node Gateway 入口存在
  - 可加载本地配置并构造 kernel client
  - 启动 agent 内核子进程，轮询 `/v1/health` 直至 ready 或超时
  - 关闭时执行 terminate → 宽限期 → kill
  - 提供可测试的生命周期编排，不提前实现 M100+ 能力
- Tests Plan:
  - unit: 需要，验证健康轮询、超时、优雅关闭降级到 kill
  - contract: 需要，验证入口模块存在
  - integration: 需要，使用 fake process / fake client 验证启动与关闭链路
  - e2e: 需要，跑最小真实入口命令，证明可启动进程、加载配置、打通 `/v1/health`
- Expected Tests:
  - `tests/unit/personal_assistant/test_main.py`
  - `tests/e2e/test_personal_assistant_main_e2e.py`
- DoD:
  - `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M98/src pytest -q` 除既有基线失败外无新增失败，且 M98 定向测试全绿
  - 完成 C1/C2/C3
  - PROGRESS 写清生命周期、探活与退出证据
