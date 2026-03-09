# M83 - 多产品架构重构十期：兼容 shim 清理与目录目标态验收

## Milestone 概述
- milestone_id: M83
- title: 多产品架构重构十期：兼容 shim 清理与目录目标态验收
- goal: 在 `products/platform/core/apps` 的 canonical 路径稳定后，系统清点并收缩遗留 shim，补齐目标目录树与迁移验收文档。
- execution_mode: serial（复用既有隔离 worktree 执行）
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M83`
- branch: `milestone/M83`
- shared dev-tasks path: `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`
- test_command: `PYTHONPATH=src python3 -m pytest -q tests/unit/test_platform_llm_providers_location.py tests/unit/test_platform_sdk_location.py tests/unit/test_apps_coding_cli_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_http_api_location.py tests/unit/test_platform_persistence_session_location.py tests/unit/test_platform_tools_location.py tests/unit/test_core_hooks_location.py tests/unit/test_core_llm_location.py tests/unit/test_core_session_location.py tests/unit/test_core_skills_location.py tests/contract/test_core_no_platform_imports.py tests/contract/test_multi_product_architecture_acceptance.py`

## 约束与边界
- 允许改动：与最终架构验收直接相关的 `src/nano_multiagent/{platform,sdk,cli,apps,session,server,products,core}/**`、对应 unit/contract tests、`多产品架构调整建议.md`、`TASKS/PROGRESS` 记录。
- 禁止改动：产品默认行为与 runtime loop 语义；与 M83 无关的 CLI/UI 体验改造；无关协议或持久化行为变更；破坏 legacy import 兼容。
- 预防规则：
  1. 以 post-M82 最终分层为准：`products/platform/core/apps` 负责 canonical ownership，legacy 路径仅在确有外部兼容价值时保留 shim。
  2. 先用测试把 ownership/acceptance/doc-linkage 变成显式红灯，再做最小实现或文档修复。
  3. 对保留的 shim 必须给出清单与 canonical 指向；对不再需要的“伪 canonical”要收口为单一真源。
  4. 保持 seed gate 已知基线可解释：`test_platform_persistence_session_location.py` 当前失败属于 M83 直接修复范围；不得掩盖其它新增失败。
  5. 文档只更新已有架构提案与里程碑记录，不额外新建无关 README/说明文件。

---

## R1 - 收口最终 canonical ownership，并把 SDK 归位到 platform

### Acceptance
1. `tests/unit/test_platform_persistence_session_location.py` 与 `tests/unit/test_core_session_location.py` 对 session store contract 的期待一致：store contract canonical home 为 `core.session.store`，平台仅持有具体持久化实现。
2. `platform/sdk` 成为 HTTP client 的 canonical home，`sdk/client.py` 降为 compatibility shim，旧 `nano_multiagent.sdk.*` 导入继续可用。
3. `apps/coding_cli`、`cli/http_client` 等应用层调用点对齐到 platform SDK canonical surface，行为不变且仍保持 HTTP-only 边界。
4. 针对 platform/core/apps 的 location tests 能同时证明 canonical ownership 与 legacy shim identity。
5. 阶段 gate 与最终 gate 全绿。

### Tests Plan
- unit: 选用。通过 location/import identity 测试锁定 session/core/platform/sdk/apps 的最终 ownership，并验证 legacy shim 不断裂。
- contract: 不单独新增。R1 重点是 ownership 与 shim 身份收口，先用 unit 测试承接。
- integration: 不单独新增。本 Roadpoint 不改 HTTP 协议与进程编排。
- e2e: 不单独新增。本次不改真实入口协议。

### Expected Tests
- `tests/unit/test_platform_persistence_session_location.py`
- `tests/unit/test_core_session_location.py`
- `tests/unit/test_platform_sdk_location.py`
- `tests/unit/test_apps_coding_cli_location.py`
- `tests/unit/test_sdk_client.py`
- 阶段 gate：`PYTHONPATH=src python3 -m pytest -q tests/unit/test_platform_persistence_session_location.py tests/unit/test_core_session_location.py tests/unit/test_platform_sdk_location.py tests/unit/test_apps_coding_cli_location.py tests/unit/test_sdk_client.py tests/contract/test_cli_http_only_contract.py`
- 最终门禁：同上 `test_command`

### DoD
- 先制造 session/platform SDK final ownership 的 Red。
- C1 仅提交测试；C2 提交实现/重构；C3 仅提交文档。
- `test_command` 全绿。
- `PROGRESS/M83-兼容-shim-清理与目录目标态验收.md` 记录决策、证据、回滚点与提交哈希。

### 状态：DONE

### 完成说明
- Red：将 `tests/unit/test_platform_persistence_session_location.py` 调整为 post-M82 最终分层预期（store contract 属于 `core.session.store`），并把 `tests/unit/test_platform_sdk_location.py`、`tests/unit/test_apps_coding_cli_location.py`、`tests/unit/test_sdk_client.py` 收口到“`platform.sdk.client` 为 canonical、`sdk.client` 为 compat shim”的断言；先触发 `ServerClient.__module__ == 'nano_multiagent.sdk.client'` 与新预期不一致的失败。
- Green：把共享 HTTP client 真实实现迁到 `src/nano_multiagent/platform/sdk/client.py`，`platform/sdk/__init__.py` 改为本地 canonical 导出，`src/nano_multiagent/sdk/client.py` 降为 compatibility shim；同时让 `apps/coding_cli/client.py` 与 `cli/http_client.py` 直接依赖 platform SDK canonical surface。
- Gate：`PYTHONPATH=src python3 -m pytest -q tests/unit/test_platform_llm_providers_location.py tests/unit/test_platform_sdk_location.py tests/unit/test_apps_coding_cli_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_http_api_location.py tests/unit/test_platform_persistence_session_location.py tests/unit/test_platform_tools_location.py tests/unit/test_core_hooks_location.py tests/unit/test_core_llm_location.py tests/unit/test_core_session_location.py tests/unit/test_core_skills_location.py tests/contract/test_core_no_platform_imports.py` 全绿（28 passed）。
- 提交序列：C1=`fd375fe`, C2=`be2f00f`, C3=`<pending>`。

---

## R2 - 补齐目标目录树、保留 shim 清单与架构验收勾稽

### Acceptance
1. 新增 architecture acceptance tests，覆盖 `products/platform/core/apps` 的目标目录树、canonical home 与 intentional shim inventory。
2. `多产品架构调整建议.md` 回写最终目标态目录树，并明确保留 shim 清单及其 canonical 指向。
3. 文档中标明 M80-M83 高优先项已完成，剩余项若未落地则明确标注 deferred 与原因。
4. 测试与文档互相勾稽：验收测试明确引用文档锚点/标题，文档也指向对应测试文件。
5. 最终 gate 全绿，且最终 shim 列表可供 main 分支长期维护。

### Tests Plan
- unit: 不单独新增。目录/文档验收更适合 contract 层。
- contract: 选用。新增目标目录树、shim inventory、文档勾稽测试，确保最终验收不只靠人工阅读。
- integration: 不单独新增。本 Roadpoint 关注静态架构与文档收口。
- e2e: 不单独新增。本次不改变用户入口主流程。

### Expected Tests
- `tests/contract/test_multi_product_architecture_acceptance.py`
- 最终门禁：同上 `test_command`

### DoD
- 先制造缺失的架构验收/文档勾稽 Red。
- C1 仅提交测试；C2 提交文档/最小实现；C3 仅提交文档记录。
- `test_command` 全绿。
- `PROGRESS/M83-兼容-shim-清理与目录目标态验收.md` 记录决策、证据、回滚点与提交哈希。

### 状态：TODO

---

## 结果目标
- `products/platform/core/apps` 的最终 canonical ownership 与目录目标态在代码、测试、文档三处一致。
- 仅保留必要 compatibility shim，且都有可审计清单与 canonical 指向。
- M80-M83 多产品架构重构链路在 `main` 上闭环，可直接作为后续架构演进基线。
