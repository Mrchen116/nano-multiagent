# PROGRESS (Milestone: M85)

- Milestone: M85
- Title: 多产品架构重构十二期：canonical wiring 实化与内部 legacy import 收口
- Worktree: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M85`
- Branch: `milestone/M85`
- Baseline:
  - Tests: `python3 -m pytest -q`
  - Result: `593 passed, 4 skipped`
- Notes:
  - 遵循 `LOGBOOK.md`：对 active runtime/canonical layers 通过 contract/import-guard 防回流；live 验收前需补完整命令与结果。
  - 遵循 `COMMENTING_GUIDE.md`：public API/docstring 写契约，注释只写意图/边界/取舍。

## Roadpoints

### R85.1 resolver/profile 驱动的 canonical wiring 打通
- Context:
  - 审计指出 loaders 已支持 `ConfigResolver`，但 live bootstrap/create_app/runtime/task 仍未把 resolver 真正贯穿到 skill/tool/hook 搜索与 profile 装配。
  - 当前 profile 模式下 runtime/task 仍可落回 `.codex/.nano/CODEX_HOME` 语义，违背 milestone 目标。
- Decision:
  - 在 `platform/bootstrap.py` 构造 `ConfigResolver` 与 profile session store，并把 resolver 挂进 `ResolvedProductConfig`，再由 `create_app(...)` 注入 runtime/tool/hook wiring。
  - 把 skill discovery 提升到 `core.skills.discovery`，由 core 只依赖 `user_skill_roots()` 协议；`skills.workspace` 退化为兼容 shim，task tool 通过 `bind_runtime()` 回填 resolver 感知。
- Rationale:
  - resolver/profile 本来就是产品级装配入口，应该在 bootstrap/app factory 一次性接通，而不是让 runtime/task 各自猜测 `.codex/.nano/CODEX_HOME`。
  - `test_core_no_platform_imports` 以源码字符串做边界扫描，所以 core discovery 不能出现任何 `nano_multiagent.platform` 字样；用协议类型能保留 resolver 能力同时维持分层约束。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M85 && /Users/czj/miniforge3/bin/python3 -m pytest -q tests/unit/test_core_skills_location.py tests/unit/test_skills_workspace_with_resolver.py tests/unit/test_platform_bootstrap.py tests/unit/test_app_factory_with_profile.py tests/unit/test_task_tool_with_resolver.py` -> `25 passed, 24 warnings in 0.51s`
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M85 && /Users/czj/miniforge3/bin/python3 -m pytest -q` -> `599 passed, 4 skipped, 246 warnings in 16.42s`
  - Entry: profile 模式下 `bootstrap_product()` 暴露 resolver/session store，`create_app()` 生成的 runtime 带 `config_resolver`，且 resolver skill 可见而 `.codex`/`CODEX_HOME` legacy skill 在 profile 路径下被排除。
- Rollback:
  - 最近稳定点：`b91a814`。
- Commits: C1=`5f25146`, C2=`b91a814`, C3=`6d8008a`
- Next:
  - 继续执行 R85.2 的 canonical import 收口、prompt ownership 回归与 import-guard 固化。

### R85.2 canonical import 收口与 product prompt ownership 实化
- Context:
  - 当前 active layer 仍存在 `session.service` / `skills.workspace` / `server.sse` / `llm.protocols.*` 等 legacy import；`products/local_coding/prompts.py` 仍反向依赖 `agent/prompting.py`。
- Decision:
  - 新增 `nano_multiagent.llm.providers.*` 作为 shared provider canonical home，让 `core.llm.factory` 只依赖 shared LLM package，不再写入 `nano_multiagent.platform` 字符串；`platform.llm.providers.*` 与旧 `llm.protocols.*` 全部改为 compatibility shim。
  - `platform/http_api/deps.py`、`platform/http_api/routes/session.py`、`runs/registry.py` 改走 canonical `nano_multiagent.session` / `platform.http_api.sse`；`products/local_coding/prompts.py` 收回 prompt 文本 ownership，`agent/prompting.py` 只保留兼容 alias。
- Rationale:
  - milestone 要求 active 层停止沿 legacy import 运行，但已有 `test_core_no_platform_imports` 又禁止 core 反向依赖 platform，因此真正的 provider canonical home 只能放在 shared `llm` 包，而不是继续把平台路径塞回 core。
  - 将 platform/providers 与 legacy/protocols 双双降为 shim，既满足新入口的 canonical import guard，也保留既有测试和外部兼容路径。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M85 && /Users/czj/miniforge3/bin/python3 -m pytest -q tests/contract/test_core_no_platform_imports.py tests/contract/test_m85_canonical_wiring_imports.py tests/unit/test_platform_llm_providers_location.py tests/unit/test_sse_encoder.py tests/unit/test_llm_anthropic_mapper.py tests/contract/test_llm_provider_contract.py` -> `29 passed, 2 warnings in 0.38s`
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M85 && /Users/czj/miniforge3/bin/python3 -m pytest -q` -> `601 passed, 4 skipped, 246 warnings in 16.33s`
  - Entry: `tests/contract/test_m85_canonical_wiring_imports.py` 证明 runtime/http_api/runs/core.llm 不再包含 legacy import；`tests/unit/test_platform_llm_providers_location.py` 证明 canonical `llm.providers.*` 与兼容 `platform.llm.providers.*`/`llm.protocols.*` 三条入口同时可用；`products/local_coding/prompts.py` 现在独立持有 prompt 文本。
- Rollback:
  - 最近稳定点：`5c3901a`。
- Commits: C1=`db9ac1b`, C2=`5c3901a`, C3=`3b68051`
- Next:
  - 执行 R85.3：跑 live 验证，完成 main 集成、board 更新与 worktree 清理。

### R85.3 full sweep、live 验证、main 集成与清理
- Context:
  - 根据技能要求，DONE 前必须跑完整 sweep，并对本 milestone 相关默认 skip live tests 给出精确命令与结果，然后 merge main / update board / remove worktree。
  - 主仓 `/Users/czj/Repos/nano-multiagent` 当前 `main` worktree 带有与 M85 无关的未提交改动，因此不能直接在该 worktree 上切换/快进 `main`；集成需要通过临时 integration branch 推到 `origin/main`，避免碰撞用户现场。
- Decision:
  - 先在 milestone worktree 上完成 full sweep + 两条 live tests 取证，再把分支 push 到 `origin/milestone/M85`，随后从 `origin/main` 创建临时 integration branch 完成 merge/push。
- Rationale:
  - 这样既满足 DONE 前必须有完整实跑证据，也能绕开主仓 dirty worktree 对 `main` checkout/merge 的阻塞，避免对用户未提交内容做 stash/restore 等未经授权的动作。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M85 && /Users/czj/miniforge3/bin/python3 -m pytest -q` -> `601 passed, 4 skipped, 246 warnings in 16.33s`
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M85 && NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 /Users/czj/miniforge3/bin/python3 -m pytest -q tests/e2e/test_anthropic_generate_e2e.py` -> `1 passed in 6.17s`
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M85 && NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 NANO_MULTIAGENT_RUN_LIVE_CLI_E2E=1 /Users/czj/miniforge3/bin/python3 -m pytest -q tests/e2e/test_cli_managed_live_agent_e2e.py` -> `1 passed in 8.85s`
  - Entry: `tests/e2e/test_anthropic_generate_e2e.py` 与 `tests/e2e/test_cli_managed_live_agent_e2e.py` 均在 live 环境通过，说明 canonical wiring 未破坏 provider generate 与 CLI managed 真实入口。
- Rollback:
  - 最近稳定点：`808a41d`。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - push `milestone/M85`，然后在 integration branch 上完成 merge/push、board 更新与 worktree 清理。
