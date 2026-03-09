# M83 Progress - 兼容 shim 清理与目录目标态验收

## 启动记录
- Milestone: `M83` / 多产品架构重构十期：兼容 shim 清理与目录目标态验收
- execution_mode: `serial`（复用既有隔离 worktree 执行）
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M83`
- branch: `milestone/M83`
- shared dev-tasks path: `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`
- gate command: `PYTHONPATH=src python3 -m pytest -q tests/unit/test_platform_llm_providers_location.py tests/unit/test_platform_sdk_location.py tests/unit/test_apps_coding_cli_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_http_api_location.py tests/unit/test_platform_persistence_session_location.py tests/unit/test_platform_tools_location.py tests/unit/test_core_hooks_location.py tests/unit/test_core_llm_location.py tests/unit/test_core_session_location.py tests/unit/test_core_skills_location.py tests/contract/test_core_no_platform_imports.py tests/contract/test_multi_product_architecture_acceptance.py`
- allowed_scope: 与最终架构验收直接相关的 `src/nano_multiagent/{platform,sdk,cli,apps,session,server,products,core}/**`、对应 unit/contract tests、`多产品架构调整建议.md`、以及本 milestone 文档记录。
- forbidden_scope: 不改产品默认行为与 runtime loop 语义；不做与 M83 无关的 CLI/UI 体验改造；不改变无关协议或持久化行为；不破坏 legacy import 兼容。
- prevention_rules:
  - 以 post-M82 最终分层为准：`products/platform/core/apps` 负责 canonical ownership，legacy 路径仅在确有外部兼容价值时保留 shim。
  - 先用测试把 ownership/acceptance/doc-linkage 变成显式红灯，再做最小实现或文档修复。
  - 对保留的 shim 必须给出清单与 canonical 指向；对不再需要的“伪 canonical”要收口为单一真源。
  - 保持 seed gate 已知基线可解释：`test_platform_persistence_session_location.py` 当前失败属于 M83 直接修复范围；不得掩盖其它新增失败。
  - 文档只更新已有架构提案与里程碑记录，不额外新建无关 README/说明文件。

## 基线
- 已按要求先阅读 `LOGBOOK.md` 与 `COMMENTING_GUIDE.md`，后续代码/文档遵守其中的注释与记录规范。
- 复用既有 `milestone/M83` worktree，当前分支为 `milestone/M83`。
- baseline seed gate：`PYTHONPATH=src python3 -m pytest -q tests/unit/test_platform_llm_providers_location.py tests/unit/test_platform_sdk_location.py tests/unit/test_apps_coding_cli_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_http_api_location.py tests/unit/test_platform_persistence_session_location.py tests/unit/test_platform_tools_location.py tests/unit/test_core_hooks_location.py tests/unit/test_core_llm_location.py tests/unit/test_core_session_location.py tests/unit/test_core_skills_location.py tests/contract/test_core_no_platform_imports.py` -> `27 passed, 1 failed`。
- 失败项：`tests/unit/test_platform_persistence_session_location.py::test_platform_persistence_session_is_canonical_home`，原因是 `SessionStore.__module__` 实际已为 `nano_multiagent.core.session.store`，与 M81-era 平台 canonical 假设冲突；该失败纳入 M83 直接修复范围。

---
