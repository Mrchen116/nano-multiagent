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
- Context: M78 只建立了 `platform.persistence.session` 的表面入口，真实 store contract/实现仍物理留在 `session/stores/*`；location test 只能证明 import 成功，不能证明 canonical ownership。
- Decision: 在 `platform/persistence/session/` 下新增 `base.py`、`jsonl_store.py`、`sqlite_store.py` 作为 canonical home，并把 `session/stores` 及其子模块全部反转为 re-export compat shim；同时把 `session.manager`、`session.service`、`server.app`、`products.base` 对齐到 canonical store contract。
- Rationale: 直接把实现搬到 platform 并让旧路径回指，是最小的物理归位方式；保留 legacy import identity 能避免上层调用者重写，同时 location tests 可以精确断言 `__module__` 已切换到 platform。
- Evidence:
  - Tests:
    - Red: `python3 -m pytest -q tests/unit/test_platform_persistence_session_location.py` -> `ModuleNotFoundError: No module named 'nano_multiagent.platform.persistence.session.base'`
    - Focused Green: `python3 -m pytest -q tests/unit/test_platform_persistence_session_location.py` -> `2 passed`
    - Gate: `python3 -m pytest -q tests/unit/test_platform_persistence_session_location.py tests/unit/test_platform_tools_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_http_api_location.py tests/unit/test_config_resolver.py tests/unit/test_tool_loader_with_resolver.py tests/unit/test_hook_loader_with_resolver.py tests/integration/test_app_bootstrap.py tests/contract/test_core_no_platform_imports.py` -> `33 passed`
  - Entry:
    - canonical home: `src/nano_multiagent/platform/persistence/session/base.py`、`jsonl_store.py`、`sqlite_store.py`
    - compat shim: `src/nano_multiagent/session/stores/__init__.py`、`base.py`、`jsonl_store.py`、`sqlite_store.py`
    - import-cycle guard: `src/nano_multiagent/session/__init__.py` 现改为 lazy export，避免 canonical store 导入 `session.entries` 时回卷到 compat shim
- Rollback: 若需重做，回退到计划提交 `909eb7f` 或测试提交 `7520c9e`，再从 canonical ownership Red 重来。
- Commits: C1=`7520c9e`, C2=`c5847ca`, C3=`<pending>`
- Next: 继续把 tools/hooks 的 loader/safety/builtins 真实实现归位到 platform，并把旧路径降为 compat shim。

### R2 tools/hooks loader/safety/builtins 物理归位到 platform
- Context: M78 只把 `platform.tools` / `platform.hooks` 暴露成 facade，真实 loader/safety/builtins 仍落在 `tools/*`、`hooks/*`；R2 的 Red 已证明 platform 导出对象 `__module__` 仍来自 legacy 路径，且 legacy builtins package 与 platform package 不是同一模块对象。
- Decision: 将 `tools.loader`、`tools.safety`、`hooks.loader` 的实现复制并反转到 `platform/tools/loader.py`、`platform/tools/safety.py`、`platform/hooks/loader.py` 作为 canonical home；新增 `platform/tools/builtins/` 与 `platform/hooks/builtins/` 真实包；旧 `tools.loader` / `tools.safety` / `hooks.loader` 改为 compat shim，旧 `tools.builtins` / `hooks.builtins` 包改为 `sys.modules` alias 指向 platform canonical package。
- Rationale: loader/safety/builtins 同时牵涉函数对象归属与 package identity，直接让 legacy 包 alias 到 platform package 能最稳地满足“旧导入继续工作、模块对象也一致”；`tools.__init__` 改 lazy export 则避免 platform builtin 引用 `tools.constants` 时经 package 初始化回卷到 compat shim 形成循环依赖。
- Evidence:
  - Tests:
    - Red: `python3 -m pytest -q tests/unit/test_platform_tools_location.py tests/unit/test_platform_hooks_location.py` -> `6 failed, 1 passed`
    - Focused Green: `python3 -m pytest -q tests/unit/test_platform_tools_location.py tests/unit/test_platform_hooks_location.py` -> `7 passed`
    - Gate: `python3 -m pytest -q tests/unit/test_platform_persistence_session_location.py tests/unit/test_platform_tools_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_http_api_location.py tests/unit/test_config_resolver.py tests/unit/test_tool_loader_with_resolver.py tests/unit/test_hook_loader_with_resolver.py tests/integration/test_app_bootstrap.py tests/contract/test_core_no_platform_imports.py` -> `30 passed`
  - Entry:
    - canonical homes: `src/nano_multiagent/platform/tools/loader.py`、`safety.py`、`builtins/**`；`src/nano_multiagent/platform/hooks/loader.py`、`builtins/**`
    - compat shims: `src/nano_multiagent/tools/loader.py`、`safety.py`、`builtins/__init__.py`；`src/nano_multiagent/hooks/loader.py`、`builtins/__init__.py`
    - caller alignment: `src/nano_multiagent/platform/bootstrap.py` 与 `src/nano_multiagent/server/app.py` 已切到 platform loader imports
- Rollback: 若需重做，回退到 R2 测试提交 `7309fe2`，或保留 R1 docs 点 `7980193` 后重新拆 loader/builtins alias。
- Commits: C1=`7309fe2`, C2=`fd35288`, C3=`<pending>`
- Next: 继续将 HTTP API app/routes 真实实现归位到 `platform/http_api`，并把 `server` 降为 compat shim。

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
