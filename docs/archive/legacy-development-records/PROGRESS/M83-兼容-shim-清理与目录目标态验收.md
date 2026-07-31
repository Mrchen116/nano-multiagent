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

### R1 收口最终 canonical ownership，并把 SDK 归位到 platform
- Context: M82 已把 shared session store contract 收口到 `core.session.store`，但 M81-era 的 `test_platform_persistence_session_location.py` 仍坚持“platform/base 是 canonical”；同时 M79 虽声明 `platform/sdk` 为目标面，但真实 HTTP client 实现仍物理留在 `sdk/client.py`，造成 platform 只是 facade、不是最终单一真源。
- Decision: 统一把 session persistence 的最终 ownership 定义为“core 持有 shared contract，platform 持有具体 store backend”；并将共享 HTTP client 的真实实现搬到 `src/nano_multiagent/platform/sdk/client.py`，让 `sdk/client.py` 降为 compatibility shim，apps/cli 直接依赖 platform SDK canonical surface。
- Rationale: session store contract 若继续声称属于 platform，会与 M82 的 core shared-kernel 边界互相矛盾；SDK 若继续以 `sdk/client.py` 为真实实现，则 `platform/sdk` 只是伪 canonical，无法满足 M83 的“最终目标态验收”。
- Evidence:
  - Tests:
    - Red: `PYTHONPATH=src python3 -m pytest -q tests/unit/test_platform_persistence_session_location.py tests/unit/test_platform_sdk_location.py tests/unit/test_apps_coding_cli_location.py tests/unit/test_sdk_client.py tests/contract/test_cli_http_only_contract.py` -> `1 failed, 22 passed`；失败为 `ServerClient.__module__ == 'nano_multiagent.sdk.client'`，说明 platform SDK 仍非 canonical home。
    - Focused Green: 同上 focused gate -> `23 passed`
    - Seed gate: `PYTHONPATH=src python3 -m pytest -q tests/unit/test_platform_llm_providers_location.py tests/unit/test_platform_sdk_location.py tests/unit/test_apps_coding_cli_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_http_api_location.py tests/unit/test_platform_persistence_session_location.py tests/unit/test_platform_tools_location.py tests/unit/test_core_hooks_location.py tests/unit/test_core_llm_location.py tests/unit/test_core_session_location.py tests/unit/test_core_skills_location.py tests/contract/test_core_no_platform_imports.py` -> `28 passed`
  - Entry:
    - canonical SDK home: `src/nano_multiagent/platform/sdk/client.py`
    - SDK compat shim: `src/nano_multiagent/sdk/client.py`
    - app/CLI alignment: `src/nano_multiagent/apps/coding_cli/client.py`、`src/nano_multiagent/cli/http_client.py`
    - final session ownership assertion: `tests/unit/test_platform_persistence_session_location.py` 与 `tests/unit/test_core_session_location.py`
- Rollback: 若需重做，回退到 R1 测试提交 `fd375fe`，或回退到计划提交 `fe3b595` 后重新拆 final ownership。
- Commits: C1=`fd375fe`, C2=`be2f00f`, C3=`1766431`
- Next: 新增 architecture acceptance / doc-linkage 契约测试，回写 `多产品架构调整建议.md` 的目标目录树与 intentional shim inventory。

### R2 补齐目标目录树、保留 shim 清单与架构验收勾稽
- Context: M80-M82 已分别完成 products/platform/core 归位，但缺少一条统一的 acceptance contract 来证明“代码目录、location tests、架构文档”三者已经对齐；`多产品架构调整建议.md` 仍停留在早期提案，没有最终目标态章节，也没有 intentional shim 清单。
- Decision: 新增 `tests/contract/test_multi_product_architecture_acceptance.py`，把最终目标目录树、保留 shim inventory、文档勾稽与 M80-M83 收口状态固化为 contract；同时在 `多产品架构调整建议.md` 追加“M83 最终目标态验收”章节，明确目录树、canonical ownership、intentional shim、deferred 项与维护原则。
- Rationale: 仅靠 location tests 还不能证明架构文档已跟上最终代码状态；把文档要点写成 contract 后，后续任何 shim 增删或目录漂移都会先在测试层暴露，避免再次出现“代码已迁移、文档还停留在旧提案”的偏差。
- Evidence:
  - Tests:
    - Red: `PYTHONPATH=src python3 -m pytest -q tests/contract/test_multi_product_architecture_acceptance.py` -> `2 failed, 1 passed`；失败点为缺失 `## 八、M83 最终目标态验收（代码/测试/文档对齐）` 与缺失 shim inventory 文档条目。
    - Focused Green: 同上 focused gate -> `3 passed`
    - Final gate: `PYTHONPATH=src python3 -m pytest -q tests/unit/test_platform_llm_providers_location.py tests/unit/test_platform_sdk_location.py tests/unit/test_apps_coding_cli_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_http_api_location.py tests/unit/test_platform_persistence_session_location.py tests/unit/test_platform_tools_location.py tests/unit/test_core_hooks_location.py tests/unit/test_core_llm_location.py tests/unit/test_core_session_location.py tests/unit/test_core_skills_location.py tests/contract/test_core_no_platform_imports.py tests/contract/test_multi_product_architecture_acceptance.py` -> `31 passed`
  - Entry:
    - acceptance contract: `tests/contract/test_multi_product_architecture_acceptance.py`
    - architecture doc: `多产品架构调整建议.md`
    - intentional shim inventory now documents `platform.product`、`platform.products.*`、`session.stores*`、`platform.persistence.session.base`、`tools.loader`、`tools.safety`、`hooks.loader`、`server*`、`sdk.client`、`cli.http_client`、`apps.coding_cli.client`、`session.*`、`hooks.*`、`skills.*`、`llm.*`
- Rollback: 若需重做，回退到 R2 测试提交 `b158926`，或回退到 R1 文档提交 `1766431` 后重新拆 acceptance/doc linkage。
- Commits: C1=`b158926`, C2=`e19211c`, C3=`<pending>`
- Next: 提交 R2 的 Green/C3，然后执行 milestone 级 rebase、merge、push、dev-tasks 更新与 worktree 清理。

---
