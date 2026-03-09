# M79 - 多产品架构重构六期：apps 归位与 CLI 入口收口

## Milestone 概述
- milestone_id: M79
- title: 多产品架构重构六期：apps 归位与 CLI 入口收口
- goal: 将 CLI 等入口按 apps 语义归位，保持 HTTP-only 边界，并清理重构兼容 shim。
- execution_mode: parallel（复用隔离 worktree，按并行执行处理）
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M79`
- branch: `milestone/M79`
- shared dev-tasks path: `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`
- test_command: `python3 -m pytest -q tests/unit/test_apps_coding_cli_location.py tests/unit/test_sdk_client.py tests/unit/test_cli_main.py tests/unit/test_cli_managed_server.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_platform_sdk_location.py`

## 约束与边界
- 允许改动：`src/nano_multiagent/apps/coding_cli/**`、`src/nano_multiagent/cli/**`、`src/nano_multiagent/sdk/client.py`、相关 unit tests、`TASKS/PROGRESS` 记录。
- 禁止改动：runtime internals 行为语义、与 M79 无关的产品目录、无关测试基线。
- 预防规则：
  1. 保持 CLI 通过 HTTP client 与 managed HTTP API 交互，不直接 import runtime internals。
  2. 兼容旧导入路径，旧 `nano_multiagent.cli.*` / `nano_multiagent.sdk.*` 表面不得破坏。
  3. managed server 只能收口到稳定 `platform.http_api` 入口，不新增旁路入口。
  4. 采用现有未提交改动，禁止丢弃/覆盖已有 M79 在制内容。

---

## R1 - 建立 apps/coding_cli 稳定表面并收口 CLI 入口

### Acceptance
1. `src/nano_multiagent/apps/coding_cli/` 提供稳定 facade，至少覆盖 `commands`、`main`、`client`、`managed_server` 与包根导出。
2. 旧 `nano_multiagent.cli` 入口继续可用，并等价指向 `apps/coding_cli` 或同一应用层实现。
3. `nano_multiagent.sdk.client` 成为 HTTP client canonical home，`cli.http_client` / `apps.coding_cli.client` 仅保留兼容 shim。
4. managed server 通过 `nano_multiagent.platform.http_api.app:create_app` 启动，本 milestone 不直接 import runtime internals。
5. 用户给定 targeted tests 全绿，且 TASKS/PROGRESS 记录包含 C1/C2/C3 提交与证据。

### Tests Plan
- unit: 选用。验证导入身份、入口归位、managed server 启动目标与 CLI 边界，反馈快且能精确锁定 facade 漂移。
- contract: 选用。通过 identity/导入路径断言校验稳定应用表面与兼容 shim 的契约不变。
- integration: 不单独新增。M79 主要是入口/模块归位，不引入新的跨进程协议；现有 CLI main/managed server 单测已覆盖关键编排链路。
- e2e: 不单独新增。当前 exit criteria 重点是稳定导入表面与 HTTP-only 边界，真实 CLI 子进程 e2e 不在本次最小改动范围内。

### Expected Tests
- `tests/unit/test_apps_coding_cli_location.py`
- `tests/unit/test_sdk_client.py`
- `tests/unit/test_cli_main.py`
- `tests/unit/test_cli_managed_server.py`
- `tests/unit/test_cli_refactor_boundaries.py`
- `tests/unit/test_platform_sdk_location.py`
- 最终门禁：`python3 -m pytest -q tests/unit/test_apps_coding_cli_location.py tests/unit/test_sdk_client.py tests/unit/test_cli_main.py tests/unit/test_cli_managed_server.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_platform_sdk_location.py`

### DoD
- 先制造一个能证明 apps/coding_cli 稳定包根表面缺失的 Red。
- C1 仅提交测试；C2 提交实现/重构；C3 仅提交文档。
- `test_command` 全绿。
- `PROGRESS/M79-apps-coding-cli-alignment.md` 记录决策、证据、回滚点与提交哈希。

### 状态：DONE

### 完成说明
- Red：新增 `test_apps_coding_cli_package_root_exports_stable_application_surface`，确认当前缺失 `apps.coding_cli` 包根稳定导出。
- Green：补齐 `apps/coding_cli/__init__.py` 稳定导出，并收口既有 apps facade / sdk canonical home / managed server platform 入口改动。
- Gate：`python3 -m pytest -q tests/unit/test_apps_coding_cli_location.py tests/unit/test_sdk_client.py tests/unit/test_cli_main.py tests/unit/test_cli_managed_server.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_platform_sdk_location.py` 全绿（113 passed）。
- 提交序列：Plan=`b5b9549`, C1=`f9558f4`, C2=`3bb991d`, C3=`<pending>`。

## 结果
- `nano_multiagent.apps.coding_cli` 成为稳定 apps-level facade，包根与子模块均可用。
- `nano_multiagent.sdk.client` 成为 canonical HTTP client home，`nano_multiagent.cli.http_client` 与 `nano_multiagent.apps.coding_cli.client` 保持兼容 shim。
- managed mode 通过 `nano_multiagent.platform.http_api.app:create_app` 启动，CLI 维持 HTTP-only 边界。
- legacy `nano_multiagent.cli` 入口持续可用，并指向 apps/application-layer surface。
