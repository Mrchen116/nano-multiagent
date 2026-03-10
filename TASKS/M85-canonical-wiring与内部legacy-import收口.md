# TASKS (Milestone: M85)

- Title: 多产品架构重构十二期：canonical wiring 实化与内部 legacy import 收口
- Goal: 让 platform/agent/runs/products 的内部 live code 改用 canonical 路径，接通 resolver/profile 驱动的真实装配，停止继续通过 legacy session/skills/server/llm 路径运行。
- Exit Criteria:
  - `bootstrap/runtime/http_api/runs/core.llm` 不再内部 import `session.service`、`skills.workspace`、`server.sse`、`llm.protocols` 与 `platform.products`。
  - `products/local_coding/prompts.py` 成为 local_coding prompt 的真实 owner，`agent/prompting.py` 只保留兼容 alias/通用渲染逻辑。
  - bootstrap/create_app/runtime/task live wiring 真正走 `ConfigResolver`/`ProductProfile`，不再退回 `.codex/.nano/CODEX_HOME` 作为 product profile 模式下的内部主路径。
  - 新增 contract/import-guard 测试，防止 active runtime/canonical layers 回流 legacy imports。
  - 里程碑 gate、必要 focused tests、full sweep 与相关默认 skip 的 live tests 全绿，并把精确命令/结果写入 `PROGRESS`。
- Baseline Test Command: `python3 -m pytest -q`
- Baseline Result: `593 passed, 4 skipped`
- Branch: `milestone/M85`
- Worktree: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M85`

## R85.1 resolver/profile 驱动的 canonical wiring 打通
- Status: DONE
  - Focused Tests: `cd /Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M85 && /Users/czj/miniforge3/bin/python3 -m pytest -q tests/unit/test_core_skills_location.py tests/unit/test_skills_workspace_with_resolver.py tests/unit/test_platform_bootstrap.py tests/unit/test_app_factory_with_profile.py tests/unit/test_task_tool_with_resolver.py` -> `25 passed`
  - Full Gate: `cd /Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M85 && /Users/czj/miniforge3/bin/python3 -m pytest -q` -> `599 passed, 4 skipped`
  - Commits: C1=`5f25146`, C2=`b91a814`, C3=`6d8008a`
  - Notes: `core.skills.discovery` 通过协议类型接收 resolver，避免 core 层源码字符串触发 `test_core_no_platform_imports`；profile 模式下 bootstrap/create_app/runtime/task 均走 resolver roots。
- Acceptance:
  - `platform/bootstrap.py` 在 profile 模式下构造并向 tool/hook live wiring 传递 `ConfigResolver`。
  - `create_app(...)` 与 `AgentRuntime` 在 profile 模式下共享/接收 resolver，runtime 默认 skill 解析不再回落到 `.codex/.nano/CODEX_HOME` 主路径。
  - active `task` built-in 在 runtime 带 resolver 时，也通过 canonical resolver skill roots 校验 `load_skills`。
  - 至少一条功能测试证明：profile workspace skill root 生效，而 legacy `.codex` 路径不再是 profile 模式下的主搜索路径。
- Tests Plan:
  - unit: 是；锁定 bootstrap/create_app/runtime/task 的 resolver 接线。
  - contract: 否；本 Roadpoint 先用行为测试证明 wiring 生效。
  - integration: 视需要；若 unit 已覆盖 app/runtime 真接线，可不额外扩。
  - e2e: 否；本点聚焦内部 wiring，不需要真实入口重跑。
- Expected Tests:
  - `tests/unit/test_platform_bootstrap.py`
  - `tests/unit/test_app_factory_with_profile.py`
  - `tests/unit/test_task_tool_with_resolver.py`（新增）
- DoD:
  - focused red -> green
  - `python3 -m pytest -q` 全绿
  - C1/C2/C3 齐全
  - `PROGRESS/M85-*.md` 记录 Context/Decision/Rationale/Evidence/Rollback/Commits/Next

## R85.2 canonical import 收口与 product prompt ownership 实化
- Status: DONE
  - Focused Tests: `cd /Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M85 && /Users/czj/miniforge3/bin/python3 -m pytest -q tests/contract/test_core_no_platform_imports.py tests/contract/test_m85_canonical_wiring_imports.py tests/unit/test_platform_llm_providers_location.py tests/unit/test_sse_encoder.py tests/unit/test_llm_anthropic_mapper.py tests/contract/test_llm_provider_contract.py` -> `29 passed`
  - Full Gate: `cd /Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M85 && /Users/czj/miniforge3/bin/python3 -m pytest -q` -> `601 passed, 4 skipped`
  - Commits: C1=`db9ac1b`, C2=`5c3901a`, C3=`TBD`
  - Notes: 引入 `nano_multiagent.llm.providers.*` 作为真正 canonical home，使 `core.llm` 远离 `platform` 字符串边界，同时 `platform.llm.providers.*` 与 `llm.protocols.*` 都退化为兼容 shim；`local_coding` prompt 文本回到 product 自有模块。

- Acceptance:
  - active runtime/canonical layers 不再内部 import `nano_multiagent.session.service`、`nano_multiagent.skills.workspace`、`nano_multiagent.server.sse`、`nano_multiagent.llm.protocols.*`。
  - `products/local_coding/prompts.py` 不再从 `agent/prompting.py` 反向导入 prompt 文本。
  - 必要的 minimal canonical homes 已落位，legacy path 仅保留兼容 shim，不做 M86/M87 删除。
  - 新增 import-guard/contract 测试，阻止未来回流到 legacy import。
- Tests Plan:
  - unit: 是；必要时补 location/alias 回归。
  - contract: 是；新增 active-layer import-guard。
  - integration: 视需要；若 create_app/runtime/task 行为已在 R85.1 锁定，可只跑受影响集。
  - e2e: 否；本点以 contract + focused unit 为主。
- Expected Tests:
  - `tests/contract/test_m85_canonical_wiring_imports.py`（新增）
  - `tests/unit/test_platform_llm_providers_location.py`
  - `tests/unit/test_product_profiles.py`
  - `tests/unit/test_sse_encoder.py`
- DoD:
  - focused red -> green
  - `python3 -m pytest -q` 全绿
  - C1/C2/C3 齐全
  - `PROGRESS/M85-*.md` 写清 canonical home 与 legacy shim 边界

## R85.3 full sweep、live 验证、main 集成与清理
- Status: TODO
- Acceptance:
  - 跑完整 `python3 -m pytest -q` 与本里程碑相关 focused tests。
  - 运行默认 skip 的相关 live tests（如适用）并把精确命令/结果写入 `PROGRESS`。
  - `milestone/M85` 成功 rebase/merge 到 `main`，push 成功。
  - 共享 `data/dev-tasks.json` 用脚本更新为 `DONE` 并记录结果。
  - 清理 `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M85` worktree。
- Tests Plan:
  - unit/contract/integration/e2e: 全量 sweep。
  - live: 跑与 provider/runtime HTTP 相关、默认 skip 的 milestone-relevant live tests。
- Expected Tests:
  - `python3 -m pytest -q`
  - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 python3 -m pytest -q tests/e2e/test_anthropic_generate_e2e.py`
  - 如 CLI managed live 与本次 wiring 相关且环境可用：`NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 NANO_MULTIAGENT_RUN_LIVE_CLI_E2E=1 python3 -m pytest -q tests/e2e/test_cli_managed_live_agent_e2e.py`
- DoD:
  - 全量与 live 命令/结果落入 `PROGRESS`
  - main merge / push / board DONE / worktree remove 全完成
