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
- Commits: C1=`7520c9e`, C2=`c5847ca`, C3=`7980193`
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
- Commits: C1=`7309fe2`, C2=`fd35288`, C3=`3c26bb0`
- Next: 继续将 HTTP API app/routes 真实实现归位到 `platform/http_api`，并把 `server` 降为 compat shim。

### R3 HTTP API app/routes 物理归位到 platform/http_api
- Context: M78 只提供了 `platform.http_api` façade，但真实 `app/auth/deps/sse/routes` 仍物理留在 `server/**`；R3 的 Red 证明 `platform.http_api.create_app.__module__` 仍来自 `nano_multiagent.server.app`。同时，M81 还必须守住 `runs/agent/session` 等 core-oriented 包不得越层依赖 `platform.http_api` 的合同。
- Decision: 将 `server/app.py`、`auth.py`、`deps.py`、`sse.py`、`routes/*.py` 整体复制并落到 `platform/http_api/**` 作为 canonical home，修复其内部对 `server.sse` 的引用为 `platform.http_api.sse`；然后把 legacy `server/**` 反转成 compat shim。`server.__init__` 改 lazy export，以便 legacy `server.sse` 等子模块还能被 core-oriented 包安全引用而不回卷导入整个 platform app package。
- Rationale: HTTP API 层内部模块互相耦合，整包复制再统一改内链，比逐个 re-export 更容易维持行为一致；而 `server.__init__` lazy export + 继续允许 core-oriented 包引用 legacy `server.sse`，可以同时满足“platform 为 canonical home”与“不让 core-oriented 包直接 import platform.http_api”的双重约束。
- Evidence:
  - Tests:
    - Red #1: `python3 -m pytest -q tests/unit/test_platform_http_api_location.py` -> `create_app.__module__ == 'nano_multiagent.server.app'`
    - Red #2: 迁移后首次 gate 失败于 `tests/contract/test_core_no_platform_imports.py`，暴露 `runs/registry.py` 直接依赖 `platform.http_api.sse`
    - Focused Green: `python3 -m pytest -q tests/unit/test_platform_http_api_location.py` -> `2 passed`
    - Gate: `python3 -m pytest -q tests/unit/test_platform_persistence_session_location.py tests/unit/test_platform_tools_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_http_api_location.py tests/unit/test_config_resolver.py tests/unit/test_tool_loader_with_resolver.py tests/unit/test_hook_loader_with_resolver.py tests/integration/test_app_bootstrap.py tests/contract/test_core_no_platform_imports.py` -> `30 passed`
  - Entry:
    - canonical homes: `src/nano_multiagent/platform/http_api/__init__.py`、`app.py`、`auth.py`、`deps.py`、`sse.py`、`routes/*.py`
    - compat shims: `src/nano_multiagent/server/__init__.py`、`app.py`、`auth.py`、`deps.py`、`sse.py`、`routes/*.py`
    - layering guard: `src/nano_multiagent/runs/registry.py` 继续依赖 legacy `nano_multiagent.server.sse`，由 compat shim 间接落到 canonical platform HTTP API，实现 ownership 迁移而不触发 core-oriented package 越层依赖
- Rollback: 若需重做，回退到 R3 测试提交 `09891c5`，或从 R2 docs 点 `3c26bb0` 重新搬运 http_api 包。
- Commits: C1=`09891c5`, C2=`04c6ba5`, C3=`39779ef`
- Next: 进行 Milestone 级集成：确保 TASKS 全 DONE、最终 gate 全绿、rebase/merge/push、更新 dev-tasks、清理 worktree。
