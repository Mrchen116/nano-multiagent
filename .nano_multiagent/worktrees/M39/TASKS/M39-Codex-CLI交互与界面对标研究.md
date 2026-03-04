# M39 - Codex CLI交互与界面对标研究

## Milestone Contract
- Milestone: `M39`
- Title: `Codex CLI交互与界面对标研究`
- Goal: 研究 `opencode-hub/codex` 的 CLI 交互与界面实现，形成 `nano_multiagent` CLI 差距矩阵与可执行改造建议。
- Scope: 仅更新 `TASKS/**` 与 `PROGRESS/**`；读取 `opencode-hub/codex/**` 与本仓 `src/nano_multiagent/cli/**`。
- Guardrail: 保留非交互命令 stdout 单 JSON 契约；区分 CLI-only 与需内核支持项。

## Baseline Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py`
- Result:
  - `67 passed, 34 warnings`

## Roadpoints

### R1 Codex CLI交互机制与界面元素清单（DONE）
- Acceptance:
  - 完成 Codex 输入机制盘点：入口模式、输入控件、slash 交互。
  - 完成 Codex 运行态反馈盘点：状态行、中断、事件展示。
  - 完成 Codex 并发交互盘点：消息队列、线程/审批并行提示。
  - 每类结论都带关键代码定位（文件+行号）。
- Tests Plan:
  - unit: 不新增；本 Roadpoint 为研究文档，不改行为代码。
  - contract: 复用既有 CLI 合同测试，保证研究输出不引入回归。
  - integration: 复用既有 CLI HTTP 流程测试。
  - e2e: 不新增；本 Roadpoint 不涉及入口行为改造。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py`
  - `tests/contract/test_cli_http_only_contract.py`
- DoD:
  - 基线门禁全绿。
  - `PROGRESS` 中给出结构化证据与代码锚点。
  - Roadpoint 状态置为 `DONE`。
- Status: `DONE`

### R2 nano CLI 对比与差距矩阵（DONE）
- Acceptance:
  - 完成 nano CLI 当前机制盘点（输入、反馈、错误、非交互契约）。
  - 输出与 Codex 的差距矩阵。
  - 必须覆盖：信息密度、可读性、运行态可交互性、错误展示、非交互模式契约。
  - 差距结论落到文件级改造点。
- Tests Plan:
  - unit: 不新增；复用门禁。
  - contract: 重点关注 `test_cli_http_only_contract.py` 的合同不回归。
  - integration: 复用 `test_cli_http_flow_integration.py`。
  - e2e: 不新增；本 Roadpoint 不做实现改动。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py`
  - `tests/contract/test_cli_http_only_contract.py`
- DoD:
  - 差距矩阵具备证据引用与改造映射。
  - 保留项（非交互 JSON 契约）明确写入。
  - Roadpoint 状态置为 `DONE`。
- Status: `DONE`

### R3 M40 可执行改造清单（CLI层优先）（DONE）
- Acceptance:
  - 输出按优先级排序的改造清单，优先 `src/nano_multiagent/cli/**`。
  - 每项都给出必须调整/新增模块与测试建议。
  - 明确哪些可仅 CLI 实现，哪些需要内核 API 支持。
  - 不实施内核改动，仅记录。
- Tests Plan:
  - unit: 不新增；本 Milestone 仅研究/设计。
  - contract: 复用合同测试守住 stdout JSON 契约。
  - integration: 复用现有 CLI HTTP 流程测试。
  - e2e: 不新增；M40 执行时补充。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py`
  - `tests/contract/test_cli_http_only_contract.py`
- DoD:
  - M40 清单可直接执行，含文件级行动项与测试入口。
  - CLI-only 与内核依赖分组清晰。
  - Roadpoint 状态置为 `DONE`。
- Status: `DONE`
