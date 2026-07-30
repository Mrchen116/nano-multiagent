# PROGRESS (Milestone: M88)

- Milestone: M88
- Title: 零残留 canonicalization：删除剩余 legacy package roots
- Worktree: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M88`
- Branch: `milestone/M88`
- Baseline:
  - Tests: `python3 -m pytest -q`
  - Result: `python3 -m pytest -q` 当前红灯（9 failed, 596 passed, 4 skipped）；失败集中在 `tests/unit/test_cli_main.py` 与 `tests/integration/test_cli_http_flow_integration.py` 仍引用已移除的 `nano_multiagent.cli.app|events|input` layered legacy paths，属于 M88 scope（authoritative base: `origin/main` commit `d912bb7`）
- Notes:
  - 目标是物理零残留，不接受最小 shim 留存。
  - source/tests/docs 需要一起改向 `core/platform/products/apps` canonical homes；README / architecture / SPEC 与 acceptance contract 必须同步收口。

## Roadpoints

### R88.1 zero-residue contract 先红
- Context:
  - M87 仍允许 minimal compatibility surface，和本里程碑“legacy roots 必须物理删除”的目标冲突；需要先把 contract/location/doc acceptance 全部改成零残留口径。
- Decision:
  - 重写 architecture acceptance、M85/M86 import guard 与各 location tests，统一断言 legacy roots 不可 import、目录必须不存在、文档必须写明 canonical entrypoints。
- Rationale:
  - 先把验收口径改红，才能稳定暴露真实差距，避免继续在过时 shim 假设上做实现。
- Evidence:
  - Tests: `python3 -m pytest -q tests/contract/test_m85_canonical_wiring_imports.py tests/contract/test_m86_canonical_homing_imports.py tests/contract/test_multi_product_architecture_acceptance.py tests/unit/test_platform_http_api_location.py tests/unit/test_apps_coding_cli_location.py tests/unit/test_core_llm_location.py tests/unit/test_platform_llm_providers_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_tools_location.py tests/unit/test_platform_session_support_location.py tests/unit/test_platform_sdk_location.py tests/unit/test_core_skills_location.py` -> `16 failed, 16 passed`
  - Entry: 红测失败点准确落在 legacy roots 仍存在、`apps/coding_cli/__init__.py`/`core/hooks/context.py` 仍有 legacy 文本、架构文档仍停留在 M87。
- Rollback:
  - 最近稳定点：`d912bb7`
- Commits: C1=`fc32839`, C2=`TBD`, C3=`TBD`
- Next:
  - 删除 legacy roots，修正 canonical wiring，并把 README/架构文档同步切到 M88 口径。

### R88.2 迁移 source/tests/docs 并物理删除 legacy roots
- Context:
  - 红测已经把零残留缺口收敛到三类：legacy roots 物理仍在、source wiring 仍残留旧包文本、README/架构文档仍引用旧入口。
- Decision:
  - 统一将 source/tests/docs 改到 `core/platform/products/apps` canonical paths；删除 `src/nano_multiagent/{cli,server,session,hooks,skills,llm,tools,sdk}`；并把 `core/llm/factory.py` 改成延迟 import provider client，避免 core 再次直接写入 `nano_multiagent.platform` 文本。
- Rationale:
  - 物理删除与源码文本收口必须同时发生，否则 `find_spec`、字符串扫描门禁和全量测试会在不同层面反复打回。
- Evidence:
  - Tests: `python3 -m pytest -q tests/contract/test_m85_canonical_wiring_imports.py tests/contract/test_m86_canonical_homing_imports.py tests/contract/test_multi_product_architecture_acceptance.py tests/unit/test_platform_http_api_location.py tests/unit/test_apps_coding_cli_location.py tests/unit/test_core_llm_location.py tests/unit/test_platform_llm_providers_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_tools_location.py tests/unit/test_platform_session_support_location.py tests/unit/test_platform_sdk_location.py tests/unit/test_core_skills_location.py` -> `32 passed`
  - Tests: `python3 -m pytest -q tests/unit/test_agent_runtime.py tests/unit/test_agent_loop.py tests/unit/test_agent_prompting.py tests/unit/test_sdk_client.py tests/contract/test_llm_provider_contract.py` -> `43 passed`
  - Tests: `python3 -m pytest -q` -> `606 passed, 4 skipped`
  - Entry: `ls src/nano_multiagent` 仅剩 `agent/apps/core/observability/platform/products/runs` 等 canonical roots；`README.md` 与 `多产品架构调整建议.md` 已统一到 `platform.http_api` / `apps.coding_cli` 入口。
- Rollback:
  - 最近稳定点：`fc32839`
- Commits: C1=`fc32839`, C2=`fb6e2cf`, C3=`TBD`
- Next:
  - 回写文档提交，随后执行 live 验证、main 集成、board 更新与 worktree 清理。

### R88.3 full sweep、live 验证、main 集成与清理
- Context:
  - focused 与全量离线门禁已经转绿；剩余工作是把 live 证据、提交哈希和集成步骤回写到文档，并完成 main 合并与清理。
- Decision:
  - 先补 live 证据与 Roadpoint 状态文档，再做文档提交，随后 rebase/merge/push 与 dev-tasks 更新。
- Rationale:
  - 文档提交需要固化最终证据链和回滚点，避免进入 main 集成后再补写导致哈希与证据漂移。
- Evidence:
  - Tests: `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 python3 -m pytest -q tests/e2e/test_anthropic_generate_e2e.py` -> `1 passed`
  - Tests: `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 NANO_MULTIAGENT_RUN_LIVE_CLI_E2E=1 python3 -m pytest -q tests/e2e/test_cli_managed_live_agent_e2e.py` -> `1 passed`
  - Entry: live proxy 与 managed CLI 入口均已按 canonical 路径实跑通过。
- Rollback:
  - 最近稳定点：`fb6e2cf`
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 提交 TASKS/PROGRESS 文档，再执行 `git fetch origin && git rebase origin/main`、merge 到 `main`、更新 board 并清理 worktree。
