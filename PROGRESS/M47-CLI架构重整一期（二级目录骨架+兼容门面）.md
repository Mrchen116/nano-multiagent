# M47 - CLI架构重整一期（二级目录骨架+兼容门面）

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `106 passed, 42 warnings`（2026-03-04）

### Plan（一次性拆分）
- Context:
  - 当前 CLI 模块已拆出多个平铺文件，但二级目录分层尚未建立，后续并行重构容易冲突。
  - 约束：只改 CLI 层，不动内核 API 与 server/runtime/core 等禁区。
- Decision:
  - 按 `R1 骨架+门面`、`R2 职责迁移+兼容`、`R3 收口验收+集成` 执行。
  - 采用“先红后绿”：先补边界红测，再迁移并保持旧 import 稳定。
- Rationale:
  - 先固化兼容门面与边界测试，可把结构性改造风险前置到自动化校验，避免行为回归。
- Evidence:
  - Tests: 基线门禁全绿（`106 passed, 42 warnings`）。
  - Entry: `run_cli` 入口和 REPL 关键路径当前行为稳定，可作为迁移对照基线。
- Rollback:
  - 回退到计划提交前稳定点。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1 红测，锁定新目录与 facade 兼容边界。

### R1 二级目录骨架与兼容导出边界
- Context:
- Decision:
  - 在 `tests/unit/test_cli_main.py` 增加红测，约束 `nano_multiagent.cli.app.commands` 存在且 `cli.commands`/`cli.main` 与其对象同一性一致。
  - 新建 `src/nano_multiagent/cli/app/`，将 `commands.py` 下沉为 `app/commands.py`，旧 `cli/commands.py` 改为兼容门面并显式转发边界测试依赖的私有符号。
- Rationale:
  - 先下沉入口编排层（`commands`）可最小化迁移影响，并为后续 `input/events/render/runtime` 迁移提供稳定锚点。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "facade_matches_new_app_commands_module"` -> `1 failed`（`ModuleNotFoundError: nano_multiagent.cli.app`）。
    - 绿测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "facade_matches_new_app_commands_module" && PYTHONPATH=src pytest -q tests/unit/test_cli_refactor_boundaries.py` -> `1 passed + 7 passed`。
    - 门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `107 passed, 42 warnings`。
  - Entry:
    - `nano_multiagent.cli.main:run_cli` 入口行为保持不变；`cli.commands` 仍可被旧路径导入。
- Rollback:
- Commits: C1=`114f1fb`, C2=`e8fbcb3`, C3=`本提交`
- Next:
  - 进入 R2：迁移 `input/events/render/runtime` 模块到二级目录并保留旧路径 facade。

### R2 按职责迁移并保持行为等价
- Context:
- Decision:
  - 先补红测 `test_cli_legacy_modules_delegate_to_layered_subpackages`，锁定 `events/input/render/runtime` 二级目录存在且旧模块对象映射到新分层模块。
  - 将 `repl_input/repl_commands` 下沉到 `cli/input/`，`repl_events` 下沉到 `cli/events/`，`context_budget/error_presenter/repl_render/turn_usage` 下沉到 `cli/render/`，`repl_runtime` 下沉到 `cli/runtime/`。
  - 保留旧路径 facade 文件（`cli/repl_*.py`、`cli/context_budget.py` 等）转发到新子目录，确保旧 import 不回归。
  - `app/commands.py` 改为优先依赖新分层模块；针对 `repl_input/repl_commands` 保持通过旧 facade 导入，确保 monkeypatch 兼容行为不变。
- Rationale:
  - 以“物理迁移 + 兼容门面”方式先搭建稳定骨架，可减少后续里程碑并行改造冲突，同时避免一次性切断旧测试依赖。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "legacy_modules_delegate_to_layered_subpackages"` -> `1 failed`（`ModuleNotFoundError: nano_multiagent.cli.events`）。
    - 子集回归：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "legacy_modules_delegate_to_layered_subpackages or facade_matches_new_app_commands_module"` -> `2 passed`。
    - 边界回归：`PYTHONPATH=src pytest -q tests/unit/test_cli_refactor_boundaries.py` -> `7 passed`。
    - 门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `108 passed, 42 warnings`。
  - Entry:
    - `run_cli`、REPL 与 `send-message` 行为保持一致；旧导入路径继续可用，新子目录导入路径已建立。
- Rollback:
- Commits: C1=`f9eb0a1`, C2=`6d6d002`, C3=`本提交`
- Next:
  - 进入 R3：执行 managed CLI 实跑验收、分支集成到 `main` 并更新 `dev_tasks` 为 DONE。

### R3 收口（门禁 + managed 实跑 + main 集成 + dev_tasks DONE）
- Context:
- Decision:
  - 在 R2 完成后复跑全量门禁，并执行 managed CLI 脚本化实跑（`/new -> bash工具请求 -> /exit`）确认入口行为稳定。
  - 以 Milestone 分支整体集成到 `main`，随后用 `dev_tasks.py update` 回填 `M47=DONE`。
- Rationale:
  - M47 为结构重整里程碑，必须通过真实 managed 入口验收来证明“仅架构重排、外部行为不变”。
- Evidence:
  - Tests:
    - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `108 passed, 42 warnings`。
  - Entry:
    - managed 验收输出片段：
      - `Tool: bash start args={"command": "echo M47_MANAGED", "timeout": 1000}`
      - `Tool: bash started status=started elapsed=0ms`
      - `Tool: bash exit code=0 status=completed duration=438ms`
      - `State: completed | stop=stop | run=...`
    - 计数：`Tool start=1, started=1, exit=1, completed=1`。
- Rollback:
- Commits: C1=`N/A`, C2=`N/A`, C3=`本提交`
- Next:
  - rebase/merge/push main，并更新 `data/dev-tasks.json` 为 `M47=DONE`。
