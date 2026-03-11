# TASKS (Milestone: M90)

- Title: Agent 内核包重命名
- Goal: 将 `src/nano_multiagent/` 重命名为 `src/agent/`，并让源码、测试、文档、打包配置全部切换到 `agent.*` canonical path，对齐 `SPEC.md` §3 与 `docs/内核设计SPEC.md` 三层结构。
- Exit Criteria:
  - `src/agent/` 包含 `core/`、`platform/`、`products/`，原 `src/nano_multiagent/` 彻底删除。
  - `pyproject.toml` 的包发现配置已切换到 `src/agent`。
  - 所有源码和测试中 `nano_multiagent.*` import 替换为 `agent.*`，并补足禁止残留的 contract/location guard。
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M90 && PYTHONPATH=src pytest -q` 全绿，且仓内无 `nano_multiagent` 残留 import（归档历史文档除外）。
  - 成功 merge `milestone/M90` -> `main`、更新共享 `data/dev-tasks.json` 为 `DONE`，并移除 `/Users/czj/Repos/nano-multiagent/.worktrees/M90`。
- Baseline Test Command: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M90 && PYTHONPATH=src pytest -q`
- Baseline Result: `1 failed, 611 passed, 4 skipped, 246 warnings`（失败原因为 `tests/contract/test_multi_product_architecture_acceptance.py` 仍读取缺失的旧架构文档 `多产品架构调整建议.md`）
- Branch: `milestone/M90`
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M90`

## R90.1 重命名目标态 contract 先红
- Status: TODO
- Acceptance:
  - architecture acceptance / location / import guard tests 改写为 M90 口径：canonical root 为 `src/agent/`，`nano_multiagent` 必须不可 import。
  - 文档与打包验收切换到 `SPEC.md`、`docs/内核设计SPEC.md`、`pyproject.toml` 的新目标态。
  - 用 focused red tests 明确暴露“目录仍在旧路径、import 仍依赖旧包”的缺口。
- Tests Plan:
  - contract：改写架构验收、残留 import guard、包发现契约。
  - unit：补齐 `agent` canonical location tests，确保 `core/platform/products` 归属新根包。
  - integration/e2e：本 Roadpoint 不跑，先固定目标态与失败点。
- Expected Tests:
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M90 && PYTHONPATH=src pytest -q tests/contract/test_multi_product_architecture_acceptance.py tests/contract/test_m85_canonical_wiring_imports.py tests/contract/test_m86_canonical_homing_imports.py tests/unit/test_core_agent_location.py tests/unit/test_platform_bootstrap.py tests/unit/test_product_profiles.py`
- DoD:
  - focused red 证据写入 `PROGRESS/M90-agent-内核包重命名.md`
  - C1 为真实 commit hash

## R90.2 物理重命名包并收口 imports
- Status: TODO
- Acceptance:
  - 物理将 `src/nano_multiagent/` 重命名为 `src/agent/`，保留 `core/`、`platform/`、`products/` 结构并删除旧根包。
  - 源码、测试、脚本中的 import 全量切到 `agent.*`，无运行期 alias/shim 兜底。
  - `pyproject.toml` 更新为 `src/agent` 包发现配置，必要文档同步到新路径。
- Tests Plan:
  - unit/contract：覆盖 runtime、tool、hook、session、product profile、HTTP API、CLI 相关 canonical imports。
  - integration/e2e：覆盖 agent runtime / HTTP / CLI / persistence 关键链路，确保重命名后真实入口仍正常。
- Expected Tests:
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M90 && PYTHONPATH=src pytest -q tests/unit tests/contract/test_agent_runtime_contract.py tests/contract/test_core_no_platform_imports.py tests/contract/test_cli_http_only_contract.py tests/integration/test_agent_runtime_integration.py tests/integration/test_bootstrap_integration.py tests/integration/test_cli_http_flow_integration.py tests/integration/test_session_flow_integration.py tests/e2e/test_agent_runtime_e2e.py tests/e2e/test_message_sync_e2e.py`
- DoD:
  - focused tests 全绿
  - `src/nano_multiagent/` 不存在，`src/agent/` 成为唯一 canonical root
  - C2 为真实 commit hash

## R90.3 全量门禁、main 集成、派工板更新与清理
- Status: TODO
- Acceptance:
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M90 && PYTHONPATH=src pytest -q` 全绿。
  - 仓内除 `docs/archive/`、历史 TASKS/PROGRESS/LOGBOOK 记录外，不再有 `nano_multiagent` import 残留；如保留历史文案需明确理由。
  - `milestone/M90` 成功 rebase/merge 到 `main` 并 push。
  - 通过脚本更新共享 `data/dev-tasks.json` 为 `DONE` 并记录结果摘要。
  - 清理 `/Users/czj/Repos/nano-multiagent/.worktrees/M90` worktree 与 `milestone/M90` 分支。
- Tests Plan:
  - authoritative：全量 `pytest -q`。
  - release：merge 前后检查 `git status` 与 `dev-tasks.json` 更新结果。
  - live：本 Milestone 无新增 live 依赖，若环境不要求则不额外跑 live case。
- Expected Tests:
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M90 && PYTHONPATH=src pytest -q`
- DoD:
  - 全量门禁、merge、board、cleanup 证据写入 `PROGRESS`
  - C3 为真实 commit hash
