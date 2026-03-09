# M81 Progress - platform 实现物理归位（session/tools/hooks/server）

## 启动记录
- Milestone: `M81` / 多产品架构重构八期：platform 实现物理归位（session/tools/hooks/server）
- execution_mode: `parallel`（复用隔离 worktree，按并行执行处理）
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M81`
- branch: `milestone/M81`
- shared dev-tasks path: `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`
- gate command: `python3 -m pytest -q tests/unit/test_platform_persistence_session_location.py tests/unit/test_platform_tools_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_http_api_location.py tests/unit/test_config_resolver.py tests/unit/test_tool_loader_with_resolver.py tests/unit/test_hook_loader_with_resolver.py tests/integration/test_app_bootstrap.py tests/contract/test_core_no_platform_imports.py`
- allowed_scope: `src/nano_multiagent/platform/persistence/session/**`、`src/nano_multiagent/platform/tools/**`、`src/nano_multiagent/platform/hooks/**`、`src/nano_multiagent/platform/http_api/**`、对应 legacy compat shim、相关 tests，与本 milestone 文档记录。
- forbidden_scope: 不改与 M81 无关的 CLI/apps/sdk 行为；不改 runtime loop 语义；不引入 app/core 对 `platform.http_api` / `platform.sdk` 的越层依赖；不破坏 legacy 导入兼容。
- prevention_rules:
  - 本次目标是 platform canonical home 物理归位，旧 `session/tools/hooks/server` 仅保留 compatibility shim。
  - 优先采用实现复制/导入反转，不做跨层重写。
  - location tests 必须固化 canonical ownership，而非只验证“能 import”。
  - `tests/contract/test_core_no_platform_imports.py` 必须持续全绿，确保 core-oriented 包不越层依赖 platform.http_api。

## 基线
- 复用既有 `milestone/M81` worktree，`data/dev-tasks.json` 已确认是指向主仓共享板 `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json` 的 symlink。
- 启动前已按要求阅读 `LOGBOOK.md` 与 `COMMENTING_GUIDE.md`，后续代码遵守 public API docstring 与“注释写意图不复述代码”的规则。
- baseline gate 已在 worktree 绝对路径下通过一次：`33 passed, 4 warnings`。

---

### R1 session persistence 物理归位到 platform/persistence/session
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:

### R2 tools/hooks loader/safety/builtins 物理归位到 platform
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:

### R3 HTTP API app/routes 物理归位到 platform/http_api
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
