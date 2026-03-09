# M79 Progress - apps 归位与 CLI 入口收口

## 启动记录
- Milestone: `M79` / 多产品架构重构六期：apps 归位与 CLI 入口收口
- execution_mode: `parallel`（复用隔离 worktree，按并行执行处理）
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M79`
- branch: `milestone/M79`
- shared dev-tasks path: `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`
- gate command: `python3 -m pytest -q tests/unit/test_apps_coding_cli_location.py tests/unit/test_sdk_client.py tests/unit/test_cli_main.py tests/unit/test_cli_managed_server.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_platform_sdk_location.py`
- allowed_scope: `src/nano_multiagent/apps/coding_cli/**`, `src/nano_multiagent/cli/**`, `src/nano_multiagent/sdk/client.py`, 对应 unit tests，与本 milestone 文档记录。
- forbidden_scope: 不改 runtime internals 行为语义；不改与 M79 无关模块；不破坏现有 CLI/SDK 兼容导入。
- prevention_rules:
  - 保持 HTTP-only CLI boundary，不直接 import runtime internals。
  - 兼容旧 `nano_multiagent.cli.*` / `nano_multiagent.sdk.*` 导入面。
  - managed server 只收口到 `nano_multiagent.platform.http_api.app:create_app`。
  - 采用既有未提交 M79 改动，不丢弃在制内容。

## 基线
- 复用既有 `milestone/M79` worktree，发现已有 apps/coding_cli、sdk/client、managed_server 方向的未提交改动。
- `data/dev-tasks.json` 使用主仓共享绝对路径 `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`；worktree 内未额外创建 `data/` 副本。
- targeted gate 已在 worktree 绝对路径下通过一次：`112 passed`。

---

### R1 apps/coding_cli 稳定表面与 CLI 入口收口
- Context: M79 已有大部分在制实现，但 `TASKS/PROGRESS` 仍是 Pending；同时 `apps.coding_cli` 包根尚未明确导出稳定 API，存在“子模块可用、包根表面不完整”的兼容缺口。
- Decision: 以单一 Roadpoint 收口本 milestone：保留既有 apps facade / sdk canonical home / managed server platform 入口改动，并补一条包根稳定导出契约测试，再以最小实现补齐包根 facade。
- Rationale: 当前未提交改动已经让主要 targeted tests 通过；额外补一条 package-root contract 可把隐性兼容缺口转成显式门禁，同时避免把 milestone 再拆成多次代码移动。
- Evidence:
  - Tests: Baseline green in reused worktree; Red/C1/C2/C3 pending.
  - Entry: `apps/coding_cli` 子模块已存在，legacy `cli.*` 入口已指向 apps/application-layer facade。
- Rollback: 若需重做，优先回退到计划提交（待补 hash），再从 package-root contract Red 重来。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 补 `apps.coding_cli` 包根 contract Red，随后分离测试/实现/文档提交。
